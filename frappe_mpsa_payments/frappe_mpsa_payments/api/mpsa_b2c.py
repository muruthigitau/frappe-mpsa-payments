from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse

import requests
from requests.auth import HTTPBasicAuth
import traceback

import frappe
import erpnext
from frappe.integrations.utils import create_request_log
from frappe.utils import get_request_site_address, nowdate
from frappe.utils.password import get_decrypted_password
import json
from ...utils.definitions import B2CRequestDefinition
from .base_class import ConnectorBaseClass, ErrorObserver
from ...utils.helpers import update_integration_request

from .payment_entry import create_payment_entry


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
            # self.authentication_token = self.authenticate()
        # saf_url = f"{self.base_url}/mpesa/b2c/v3/paymentrequest"
        saf_url = "http://192.168.1.48:8050/mpesa/b2c/v3/paymentrequest"
        # callback_url = (
        #     f"https://{urlparse(get_request_site_address(full_address=True)).hostname}"
        #     "/api/method/frappe_mpsa_payments.frappe_mpsa_payments.api.mpsa_b2c.results_callback_url"
        # )
        callback_url = (
            "http://192.168.1.48:8001/api/method/frappe_mpsa_payments.frappe_mpsa_payments.api.mpsa_b2c.results_callback_url"
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
    originator_conversation_id = result.get("OriginatorConversationID")
    
    result_json = json.dumps(result)

    try:
        mpesa_b2c_payment_item = frappe.get_doc("MPesa B2C Employee Payment Item", {"originator_conversation_id": originator_conversation_id})
        mpesa_b2c_payment = frappe.get_doc(mpesa_b2c_payment_item.parenttype, mpesa_b2c_payment_item.parent)

        if result.get("ResultCode") != 0:
            update_integration_request(
                originator_conversation_id,
                "Failed",
                output=result_json,
                error=result.get("ResultDesc"),
            )
            frappe.log_error(f"B2C Request failed: {result.ResultDesc}", "Mpesa B2C Error")

            mpesa_b2c_payment_item.payment_status = "Failed"
            mpesa_b2c_payment_item.error_code = result.get("errorCode")
            mpesa_b2c_payment_item.error_message = result.get("ResultDesc") or result.get("errorMessage")

        else:
            update_integration_request(
                originator_conversation_id,
                "Completed",
                output=result_json,
            )

            # TODO: create an Mpesa B2C Transactions Entry

            mpesa_b2c_payment_item.payment_status = "Success"
            mpesa_b2c_payment_item.save(ignore_permissions=True)

            frappe.enqueue(
                "frappe_mpsa_payments.frappe_mpsa_payments.api.mpsa_b2c.handle_successful_payment",
                queue="long",
                timeout=600,
                parent_doc=mpesa_b2c_payment,
                child_doc=mpesa_b2c_payment_item
            )

        mpesa_b2c_payment_item.save(ignore_permissions=True)
        frappe.db.commit()

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Failed to update payment_status in callback")

    return "Success"


def handle_successful_payment(parent_doc, child_doc):
    """
    Trigger follow-up accounting entries based on reference doctype.
    This function will be enqueued and run in the background.
    """

    try:
        match child_doc.reference_doctype:
            case "Salary Slip":
                create_journal_entry(parent_doc, child_doc) # TODO: create helper functions for this
            case "Employee Advance" | "Expense Claim" | "Purchase Invoice":
                creat_payment_entry_for_doc(parent_doc, child_doc) # TODO: create helper functions for this
            case _:
                frappe.log_error(
                    f"Unsupported reference_doctype: {child_doc.reference_doctype}",
                    "Payment Callback Handler"
                )
    except Exception as e:
        error_msg = f"Error handling payment for {child_doc.name}: {str(e)}"
        error_msg = error_msg
        frappe.log_error(frappe.get_traceback(), "MPesa B2C Employee Payment Item")
        frappe.db.set_value(
            'MPesa B2C Employee Payment Item', 
            child_doc.name, 
            {
                "error_code": "500",
                "error_description": str(e)
            }
        )
        frappe.db.commit()


def create_journal_entry(parent_doc, child_doc):
    pass

def creat_payment_entry_for_doc(parent_doc, child_doc):
    party_type = "Employee" if child_doc.reference_doctype in ["Employee Advance", "Expense Claim"] else "Supplier"
    party = frappe.db.get_value(party_type, child_doc.receiver_name, "name")
    amount = child_doc.amount

    company = parent_doc.company
    currency = frappe.db.get_value('Company', company, 'default_currency')

    mpesa_setting = parent_doc.get('mpesa_setting')
    mode_of_payment = frappe.db.get_value("Mode of Payment", f"Mpesa-{mpesa_setting}", "name")

    payment_entry = create_payment_entry(
        company,
        party,
        amount,
        currency,
        mode_of_payment,
        party_type=party_type,
        reference_date=nowdate(),
        reference_no=child_doc.originator_conversation_id,
        posting_date=nowdate(),
        cost_center=erpnext.get_default_cost_center(company),
        submit=0
    )

    payment_entry.append('references', {
        'reference_doctype': child_doc.reference_doctype,
        'reference_name': child_doc.record,
        'allocated_amount': child_doc.amount
    })

    # if not payment_entry.docstatus:
    #     payment_entry.insert()
    #     payment_entry.submit()

    frappe.msgprint(f'Payment Entry {payment_entry.name} created for {child_doc.reference_doctype} {child_doc.record}')