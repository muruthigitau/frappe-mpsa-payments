from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse

import requests
from requests.auth import HTTPBasicAuth
import traceback

import frappe
from frappe.integrations.utils import create_request_log
from frappe.utils import get_request_site_address
from frappe.utils.password import get_decrypted_password
import json
from ...utils.definitions import B2CRequestDefinition
from .base_class import ConnectorBaseClass, ErrorObserver
from ...utils.helpers import update_integration_request


class URLS(Enum):
    """URLs Constant Exporting class"""

    SANDBOX = "https://sandbox.safaricom.co.ke"
    PRODUCTION = "https://api.safaricom.co.ke"


class MpesaB2CConnector(ConnectorBaseClass):
    """MPesa B2C Connector Class"""

    def __init__(self, env="sandbox", app_key=None, app_secret=None):
        """Setup configuration for Mpesa connector and generate new access token."""
        super().__init__()

        self.authentication_token = None
        self.expires_in = None

        self.env = env
        self.app_key = app_key
        self.app_secret = app_secret

        self.base_url = URLS.SANDBOX.value if env == "sandbox" else URLS.PRODUCTION.value

        self.attach(ErrorObserver())

    def authenticate(self) -> str:
        """Fetch a new access token from MPesa API."""
        authenticate_uri = "/oauth/v1/generate?grant_type=client_credentials"
        authenticate_url = f"{self.base_url}{authenticate_uri}"
        
        # Use the app credentials to fetch the token
        response = requests.get(
            authenticate_url,
            auth=HTTPBasicAuth(self.app_key, self.app_secret),
            timeout=60,
        )
        
        # Handle API response
        if response.status_code == 200:
            data = response.json()
            self.authentication_token = data["access_token"]
            self.expires_in = datetime.now() + timedelta(seconds=int(data["expires_in"]))
            return self.authentication_token
        else:
            error_msg = f"Failed to authenticate: {response.status_code} - {response.text}"
            frappe.throw(error_msg)

    def make_b2c_payment_request(self, request_data: B2CRequestDefinition) -> dict:
        """Make a B2C Payment Request."""
        # Ensure token is valid or fetch a new one
        if not self.authentication_token or datetime.now() >= self.expires_in:
            self.app_key = request_data.ConsumerKey
            self.app_secret = request_data.ConsumerSecret
            self.authentication_token = self.authenticate()
        saf_url = f"{self.base_url}/mpesa/b2c/v3/paymentrequest"
        callback_url = (
            f"https://{urlparse(get_request_site_address(full_address=True)).hostname}"
            "/api/method/frappe_mpsa_payments.frappe_mpsa_payments.api.mpsa_b2c.results_callback_url"
        )

        payload_dict = {
        **request_data.to_dict(), 
        "QueueTimeOutURL": callback_url,
        "ResultURL": callback_url,
    }

        headers = {
            "Authorization": f"Bearer {self.authentication_token}",
            "Content-Type": "application/json",
        }

        # Log the integration request
        integration_request_name = create_request_log(
            url=saf_url,
            is_remote_request=1,
            data=payload_dict,
            service_name="Mpesa B2C",
            name=request_data.OriginatorConversationID,
            error=None,
            request_headers=headers,
        ).name
        try:
            response = requests.post(
                saf_url,
                json=payload_dict,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            self.error = e
            # self.notify()
            error_msg = f"HTTP error during B2C request: {e.response.status_code} - {e.response.text}"
            frappe.log_error(error_msg, "Error")
            frappe.throw(error_msg)
        except Exception as e:
            error_msg = (
                f"Unexpected error: {str(e)}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            frappe.log_error(error_msg, "Mpesa B2C UnexpectedError")
            frappe.throw("An unexpected error occurred during the B2C request. Please check the error log.")


@frappe.whitelist(allow_guest=True)
def results_callback_url(**kwargs) -> dict:
    """Handle the callback from MPesa API."""
    result = frappe._dict(kwargs["Result"])
    
    result_json = json.dumps(result)
    if result.get("ResultCode") != 0:
        update_integration_request(
            result.get("OriginatorConversationID"),
            "Failed",
            output=result_json,
            error=result.get("ResultDesc"),
        )
        frappe.log_error(f"B2C Request failed: {result.ResultDesc}", "Mpesa B2C Error")
    else:
        print(str(result))
        update_integration_request(
            result.get("OriginatorConversationID"),
            "Completed",
            output=result_json,
        )
    return "Success"
