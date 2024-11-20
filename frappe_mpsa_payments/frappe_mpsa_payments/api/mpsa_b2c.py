from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse

import requests
from requests.auth import HTTPBasicAuth

import frappe
from frappe.integrations.utils import create_request_log
from frappe.utils import get_request_site_address
from frappe.utils.password import get_decrypted_password

from ...utils.definitions import B2CRequestDefinition
from ...utils.doctype_names import DARAJA_ACCESS_TOKENS_DOCTYPE
from ...utils.helpers import save_access_token, update_integration_request

from .base_class import ConnectorBaseClass, ErrorObserver


class URLS(Enum):
    """URLS Constant Exporting class"""

    SANDBOX = "https://sandbox.safaricom.co.ke"
    PRODUCTION = "https://api.safaricom.co.ke"


class MpesaB2CConnector(ConnectorBaseClass):
    """MPesa B2C Connector Class"""

    def __init__(
        self,
        env: str = "sandbox",
        app_key: bytes | str | None = None,
        app_secret: bytes | str | None = None,
    ) -> None:
        """Setup configuration for Mpesa connector and generate new access token."""
        super().__init__()

        self.authentication_token = None
        self.expires_in = None

        self.env = env
        self.app_key = app_key
        self.app_secret = app_secret

        if env == "sandbox":
            self.base_url = URLS.SANDBOX.value
        else:
            self.base_url = URLS.PRODUCTION.value

        self.attach(ErrorObserver())

    def authenticate(self, setting: str) -> dict[str, str | datetime] | None:
        """Authenticate at following endpoint:
        https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials (for sandbox)

        Args:
            setting (str): The Mpesa Settings record to fetch Credentials from

        Returns:
            dict[str, str | datetime] | None: The fetched response if request was successful.
            Otherwise an error is raised.
        """
        authenticate_uri = "/oauth/v1/generate?grant_type=client_credentials"
        authenticate_url = f"{self.base_url}{authenticate_uri}"

        r = requests.get(
            authenticate_url,
            auth=HTTPBasicAuth(self.app_key, self.app_secret),
            timeout=120,
        )

        if r.status_code < 400:
            # Success state
            response = r.json()

            self.authentication_token = response["access_token"]
            self.expires_in = datetime.now() + timedelta(
                seconds=int(response["expires_in"])
            )
            fetch_time = datetime.now()

            # Save access token details
            # save_access_token(
            #     token=self.authentication_token,
            #     expiry_time=self.expires_in,
            #     fetch_time=fetch_time,
            #     associated_setting=setting,
            # )

            # return {
            #     "access_token": self.authentication_token,
            #     "expires_in": self.expires_in,
            #     "fetched_time": fetch_time,
            # }
            return self.authentication_token

        # Failure State
        # frappe.throw(
        #     f"Can't get token with provided Credentials for setting: <b>{setting}</b>",
        #     title="Error",
        # )

    def make_b2c_payment_request(
        self, request_data: B2CRequestDefinition
    ) -> str | None:
        """Initiates a B2C Payment Request to Daraja at following link:
        https://sandbox.safaricom.co.ke/mpesa/b2c/v3/paymentrequest (for sandbox)

        Args:
            request_data (B2CRequestDefinition): The data used to generate the request JSON

        Returns:
            str | None: The Initial response after making the request
        """
        # Check if valid Access Token exists
        # token = frappe.db.get_value(
        #     DARAJA_ACCESS_TOKENS_DOCTYPE,
        #     {
        #         "associated_settings": request_data.Setting,
        #         "expiry_time": [">", datetime.now()],
        #     },
        #     ["name", "access_token"],
        #     as_dict=True,
        # )
        token = self.authenticate(request_data.Setting)
        if not token:
            # If no valid token is present in DB
            self.app_key = request_data.ConsumerKey
            self.app_secret = request_data.ConsumerSecret

            # Fetch and save credentials
            self.authentication_token = self.authenticate(request_data.Setting)[
                "access_token"
            ]

        else:
            self.authentication_token = get_decrypted_password(
                DARAJA_ACCESS_TOKENS_DOCTYPE, token.name, "access_token"
            )

        saf_url = f"{self.base_url}/mpesa/b2c/v3/paymentrequest"
        # callback_url = f"https://{urlparse(get_request_site_address(full_address=True)).hostname}/api/method/navari_mpesa_b2c.mpesa_b2c.scripts.server.mpesa_connector.results_callback_url"
        
        callback_url = f"https://{urlparse(get_request_site_address(full_address=True)).hostname}/api/method/frappe_mpsa_payments.frappe_mpsa_payments.api.mpsa_b2c.results_callback_url"

        payload = request_data.to_json(
            {
                "QueueTimeOutURL": callback_url,
                "ResultURL": callback_url,
            }
        )
        headers = {
            "Authorization": f"Bearer {self.authentication_token}",
            "Content-Type": "application/json",
        }

        # Create Integration Request
        self.integration_request = create_request_log(
            url=saf_url,
            is_remote_request=1,
            data=payload,
            service_name="Mpesa",
            name=request_data.OriginatorConversationID,
            error=None,
            request_headers=headers,
        ).name

        try:
            response = requests.post(
                saf_url,
                data=payload,
                headers=headers,
                timeout=60,
            )

            response.raise_for_status()

        except (requests.HTTPError, requests.ConnectionError) as e:
            self.error = e
            self.notify()

        return response.json()


@frappe.whitelist(allow_guest=True)
def results_callback_url(**kwargs) -> None:
    """Callback URL"""
    result = frappe._dict(kwargs["Result"])

    if result.ResultCode != 0:
        # If Failure Response
        update_integration_request(
            result.OriginatorConversationID,
            "Failed",
            output=result,
            error=result.ResultDesc,
        )
    return result
