from typing import Callable, Optional, Union, Literal
from urllib import parse
from datetime import datetime, timedelta
from decimal import Decimal
import json
import requests
from requests.auth import HTTPBasicAuth
import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
import pytz
from ...utils.model_imports import MpesaSettings, IntegrationRequest

logger = logging.getLogger(__name__)

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

def on_mpesa_error(data, url, doctype, document_name):
    error_msg = f"Remote error at {url} for {doctype} {document_name}: {data}"
    logger.error(error_msg)

def update_integration_request(
    integration_request_id: str,
    status: Literal["Completed", "Failed"],
    output: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    try:
        with transaction.atomic():
            doc = IntegrationRequest.objects.select_for_update().get(pk=integration_request_id)
            
            if error:
                doc.error = error if doc.error in (None, "null") else (doc.error + "\n" + error)
            
            if output:
                doc.output = output if doc.output in (None, "null") else (doc.output + "\n" + output)
            
            doc.status = status
            doc.save()
    except Exception as e:
        logger.error(f"Failed to update integration request: {e}")
        raise

class ErrorObserver:
    def update(self, notifier: 'BaseMpesaConnector'):
        if notifier.error:
            name = getattr(notifier.integration_request, "id", None)
            if name:
                update_integration_request(name, status="Failed", error=str(notifier.error))
            logger.error(
                f"Mpesa Fatal Error: {str(notifier.error)}",
                extra={
                    'reference_doctype': notifier.doctype,
                    'reference_name': notifier.document_name
                }
            )
            raise ValidationError("A Fatal Error occurred. Check the Error Log.")

class BaseMpesaConnector:
    def __init__(self):
        self.integration_request: Optional[Union[str, IntegrationRequest]] = None
        self.error: Optional[Union[str, Exception]] = None
        self._observers: list[ErrorObserver] = [ErrorObserver()]
        self.doctype: Optional[Union[str, object]] = None
        self.document_name: Optional[str] = None

    def notify(self):
        for observer in self._observers:
            observer.update(self)

class MpesaConnector(BaseMpesaConnector):
    
    def __init__(self, settings_name: str):
        super().__init__()
        self.settings_name = settings_name
        self._endpoint: Optional[str] = None
        self._payload: Optional[dict] = None
        self._method: Optional[Literal["GET", "POST", "PATCH", "PUT"]] = None
        self._success_callback: Optional[Callable] = None
        self._error_callback: Optional[Callable] = None
        self._request_description: Optional[str] = None
        self._custom_headers: dict = {}
        self._base_url: Optional[str] = None
        self._url: Optional[str] = None
        self._reuse_existing_integration_request: bool = False

    def _get_mpesa_settings(self) -> dict:
        if not self.settings_name:
            raise ValidationError("Mpesa Settings name is required.")

        try:
            s = MpesaSettings.objects.get(pk=self.settings_name)
            return {
                "consumer_key": s.consumer_key,
                "consumer_secret": s.consumer_secret,
                "access_token": s.access_token,
                "token_expiry": s.token_expiry,
                "sandbox": s.sandbox,
            }
        except MpesaSettings.DoesNotExist:
            raise ValidationError(f"Mpesa Settings {self.settings_name} not found")

    def _initialize_settings(self):
        settings = self._get_mpesa_settings()
        self._base_url = "https://sandbox.safaricom.co.ke" if settings["sandbox"] else "https://api.safaricom.co.ke"

    def _is_token_valid(self) -> bool:
        settings = self._get_mpesa_settings()
        if not settings["access_token"] or not settings["token_expiry"]:
            return False
        
        now = timezone.now()
        expiry = settings["token_expiry"]
        
        if timezone.is_naive(expiry):
            expiry = timezone.make_aware(expiry, timezone=pytz.UTC)
        
        return now < expiry

    def _update_token(self, token: str, expires_in: int):
        token_expiry = timezone.now() + timedelta(seconds=int(expires_in))
        with transaction.atomic():
            settings = MpesaSettings.objects.select_for_update().get(pk=self.settings_name)
            settings.access_token = token
            settings.expires_in = int(expires_in)
            settings.token_expiry = token_expiry
            settings.save()

    def authenticate(self) -> str:
        self._initialize_settings()
        s = self._get_mpesa_settings()
        url = f"{self._base_url}/oauth/v1/generate?grant_type=client_credentials"
        r = requests.get(url, auth=HTTPBasicAuth(s["consumer_key"], s["consumer_secret"]))
        r.raise_for_status()
        data = r.json()
        self._update_token(data["access_token"], data["expires_in"])
        return data["access_token"]

    def _get_authenticated_headers(self) -> dict:
        if not self._is_token_valid():
            self.authenticate()
        token = self._get_mpesa_settings()["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        headers.update(self._custom_headers)
        return headers

    def make_remote_call(self, doctype=None, document_name=None, retrying=False):
        if not all([self._endpoint, self._method, self._success_callback]):
            raise ValidationError("Missing required parameters (endpoint, method, callbacks).")

        self._initialize_settings()
        self._url = f"{self._base_url}/{self._endpoint.lstrip('/')}"
        self.doctype, self.document_name = doctype, document_name

        if not retrying:
            if self._reuse_existing_integration_request:
                existing_request = IntegrationRequest.objects.filter(
                    reference_docname=document_name,
                    request_description=self._request_description,
                ).order_by('-creation').first()
                
                if existing_request:
                    self.integration_request = existing_request
                else:
                    self.integration_request = self._create_integration_request()
            else:
                self.integration_request = self._create_integration_request()

        try:
            response = self._send_request()
            logger.debug(f"MPesa API Response: {response.status_code} - {response.text}")
            data = self._get_response_data(response)

            if response.status_code in {200, 201}:
                self._handle_success(data)
            else:
                self._handle_error(data)
            return data

        except requests.RequestException as e:
            logger.error(f"MPesa API Request failed: {str(e)}")
            self.error = e
            self.notify()
            return None

    def _create_integration_request(self) -> IntegrationRequest:
        return IntegrationRequest.objects.create(
            data=json.dumps(self._payload, cls=DecimalEncoder),
            request_description=self._request_description,
            is_remote_request=True,
            integration_request_service="Mpesa",
            request_headers=json.dumps(self._get_authenticated_headers()),
            url=self._url,
            reference_docname=self.document_name,
        )

    def _send_request(self) -> requests.Response:
        headers = self._get_authenticated_headers()
        json_payload = json.dumps(self._payload, cls=DecimalEncoder)
     
        method_map = {
            "GET": lambda: requests.get(self._url, headers=headers, params=self._payload),
            "POST": lambda: requests.post(self._url, data=json_payload, headers=headers),
            "PATCH": lambda: requests.patch(self._url, data=json_payload, headers=headers),
            "PUT": lambda: requests.put(self._url, data=json_payload, headers=headers),
        }

        if self._method in {"PATCH", "PUT"} and self._payload and "id" in self._payload:
            rid = self._payload.pop("id")
            if f"/{rid}/" not in self._url:
                self._url = f"{self._url.rstrip('/')}/{rid}/"

        return method_map[self._method]()

    def _get_response_data(self, response: requests.Response) -> Optional[Union[dict, str, bytes]]:
        content_type = response.headers.get("Content-Type", "").lower()
        if "json" in content_type:
            try:
                return response.json()
            except ValueError:
                logger.error(f"Failed to parse JSON response: {response.text}")
                return None
        if "text" in content_type or "xml" in content_type:
            return response.text.strip() or None
        if any(mime in content_type for mime in ["octet-stream", "pdf", "zip"]):
            return response.content
        return None

    def _handle_success(self, data):
        try:
            self._success_callback(
                response=data,
                payload=self._payload,
                document_name=self.document_name,
                doctype=self.doctype,
                integration_request=self.integration_request,
                settings_name=self.settings_name
            )
            update_integration_request(
                str(self.integration_request.id),
                status="Completed",
                output=json.dumps(data, cls=DecimalEncoder)
            )
        except Exception as e:
            logger.error(f"Error in success callback: {str(e)}")
            raise

    def _handle_error(self, data):
        try:
            update_integration_request(
                str(self.integration_request.id),
                status="Failed",
                error=json.dumps(data, cls=DecimalEncoder)
            )
            if self._error_callback:
                self._error_callback(
                    response=data,
                    payload=self._payload,
                    document_name=self.document_name,
                    doctype=self.doctype,
                    integration_request=self.integration_request,
                    settings_name=self.settings_name
                )
            else:
                on_mpesa_error(
                    data,
                    url=self._url,
                    doctype=self.doctype,
                    document_name=self.document_name
                )
        except Exception as e:
            logger.error(f"Error in error handling: {str(e)}")
            raise

    # Builder pattern methods
    def set_headers(self, headers: dict):
        self._custom_headers.update(headers)
        return self

    def set_endpoint(self, endpoint: str):
        self._endpoint = endpoint
        return self

    def set_payload(self, payload: dict):
        self._payload = payload
        return self

    def set_method(self, method: Literal["GET", "POST", "PATCH", "PUT"]):
        self._method = method
        return self

    def on_success(self, callback: Callable):
        self._success_callback = callback
        return self

    def on_error(self, callback: Callable):
        self._error_callback = callback
        return self

    def describe(self, description: str):
        self._request_description = description
        return self
    
    def reuse_existing_request(self, flag: bool = True):
        self._reuse_existing_integration_request = flag
        return self