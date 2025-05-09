from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse


import frappe
import erpnext
from frappe.model.document import Document
from frappe.integrations.utils import create_request_log
from frappe.utils import get_request_site_address, nowdate, get_datetime
from frappe.utils.password import get_decrypted_password
import json
from ...utils.definitions import B2CRequestDefinition
from ..connectors.connectors import MpesaConnector, update_integration_request

from .payment_entry import create_payment_entry


class URLS(Enum):
    """URLs Constant Exporting class"""

    SANDBOX = "https://sandbox.safaricom.co.ke"
    PRODUCTION = "https://api.safaricom.co.ke"


class MpesaB2CConnector(MpesaConnector):
    """MPesa B2C Connector Class"""

    def __init__(self, settings_name: str):
        """Initialize with Mpesa Settings name."""
        super().__init__(settings_name=settings_name)

        self.base_url = URLS.SANDBOX.value if self._get_mpesa_settings()["sandbox"] else URLS.PRODUCTION.value

    def make_b2c_payment_request(self, request_data: B2CRequestDefinition, doctype: str, document_name: str) -> dict:
        """Make a B2C Payment Request."""

        callback_url = (
            f"https://{urlparse(get_request_site_address(full_address=True)).hostname}"
            "/api/method/frappe_mpsa_payments.frappe_mpsa_payments.api.mpsa_b2c.results_callback_url"
        )

        payload = {
            **request_data.to_dict(), 
            "QueueTimeOutURL": callback_url,
            "ResultURL": callback_url,
        }

        if frappe.db.exists("Integration Request", request_data.OriginatorConversationID):
            existing_request = frappe.get_doc("Integration Request", request_data.OriginatorConversationID)
            if existing_request.status in ["Completed", "Failed"]:
                frappe.throw(
                    f"Integration Request with OriginatorConversationID {request_data.OriginatorConversationID} already exists."
                )
                self.integration_request = existing_request

        else:
            try:
                self.integration_request = create_request_log(
                    data=payload,
                    request_description=self._request_description,
                    is_remote_request=True,
                    service_name="Mpesa B2C",
                    request_headers=self._get_authenticated_headers(),
                    url=f"{self.base_url}/mpesa/b2c/v3/paymentrequest",
                    reference_docname=document_name,
                    reference_doctype=doctype,
                    name=request_data.OriginatorConversationID,
                )
            except frappe.exceptions.DuplicateEntryError:
                frappe.throw(
                    f"Integration Request with OriginatorConversationID {request_data.OriginatorConversationID} already exists."
                )

        def success_callback(response, **kwargs):
            """Handle successful B2C respnose."""
            update_integration_request(
                kwargs["integration_request"].name,
                "Completed",
                output=json.dumps(response),
            )
            frappe.db.commit()

        def error_callback(response, **kwargs):
            """Handle B2C error response."""
            error_msg = f"B2C Request failed: {response.get('errorMessage', 'Unknown error')}"

            update_integration_request(
                kwargs["integration_request"].name,
                "Failed",
                error=error_msg,
                output=json.dumps(response),
            )
            frappe.log_error(error_msg, "Mpesa B2C Error")

        self.set_endpoint("mpesa/b2c/v3/paymentrequest") \
            .set_payload(payload) \
            .set_method("POST") \
            .describe(f"B2C Payment Request for {document_name}") \
            .on_success(success_callback) \
            .on_error(error_callback)

        return self.make_remote_call(doctype=doctype, document_name=document_name, skip_integration_request=True)


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
            mpesa_b2c_payment_item.payment_status = "Failed"
            mpesa_b2c_payment_item.error_code = result.get("errorCode")
            mpesa_b2c_payment_item.error_message = result.get("ResultDesc") or result.get("errorMessage")
            
            update_integration_request(
                originator_conversation_id,
                "Failed",
                output=result_json,
                error=result.get("ResultDesc") or result.get("errorMessage"),
            )
            frappe.log_error(f"B2C Request failed: {result.ResultDesc}", "Mpesa B2C Error")


        else:
            create_mpesa_transaction_entry(result, mpesa_b2c_payment, mpesa_b2c_payment_item)

            mpesa_b2c_payment_item.payment_status = "Success"
            mpesa_b2c_payment_item.save(ignore_permissions=True)
            
            update_integration_request(
                originator_conversation_id,
                "Completed",
                output=result_json,
            )


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


def create_mpesa_transaction_entry(result: dict, b2c_payment_doc: Document, b2c_payment_item_doc: Document):
    """
    Store a successful B2C transaction callback into MPesa B2C Payments Transactions.
    :param result: Dictionary parsed from Safaricom's B2C callback (Success).
    :param b2c_payment_doc: The parent MPesa B2C Payment document.
    :param b2c_payment_item_doc: The item/transaction with a successful response.
    """

    try:
        transaction_data = result.get("ResultParameters", {}).get("ResultParameter", [])
        param_dict = {p["Key"]: p["Value"] for p in transaction_data}

        transaction_id = result.get("TransactionID")
        receiver_public_name = param_dict.get("ReceiverPartyPublicName")
        transaction_amount = float(param_dict.get("TransactionAmount", 0.0)) 
        transaction_completed_datetime = param_dict.get("TransactionCompletedDateTime")
        recipient_is_registered_customer = param_dict.get("B2CRecipientIsRegisteredCustomer")
        working_acct_avlbl_funds = param_dict.get("B2CWorkingAccountAvailableFunds")
        charges_paid = float(param_dict.get("B2CChargesPaidAccountAvailableFunds", 0.0))
        utility_funds = float(param_dict.get("B2CUtilityAccountAvailableFunds", 0.0))

        account_paid_from = b2c_payment_doc.account_paid_from

        if frappe.db.exists("MPesa B2C Payments Transactions", transaction_id):
            frappe.throw(f"Transaction with ID {transaction_id} already exists.")

        doc = frappe.new_doc("MPesa B2C Payments Transactions")
        doc.b2c_payment_name = b2c_payment_doc.name
        doc.b2c_payment_item_name = b2c_payment_item_doc.name
        doc.transaction_id = transaction_id
        doc.transaction_amount = transaction_amount
        doc.receiver_public_name = receiver_public_name
        doc.recipient_is_registered_customer = recipient_is_registered_customer
        doc.charges_paid_acct_avlbl_funds = charges_paid
        doc.working_acct_avlbl_funds = working_acct_avlbl_funds
        doc.utility_acct_avlbl_funds = utility_funds
        doc.transaction_completed_datetime = get_datetime(transaction_completed_datetime)
        doc.account_paid_from = account_paid_from

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "B2C Payment Transaction Save Failed")


def create_journal_entry(parent_doc, child_doc):
    pass

def creat_payment_entry_for_doc(parent_doc, child_doc):
    party_type = "Employee" if child_doc.reference_doctype in ["Employee Advance", "Expense Claim"] else "Supplier"
    party_account = parent_doc.account_paid_to if parent_doc.doctype_to_pay_against == "Employee Advance" else None
    party = frappe.db.get_value(party_type, child_doc.receiver_name, "name")
    amount = child_doc.amount

    company = parent_doc.company
    currency = frappe.db.get_value('Company', company, 'default_currency')

    mpesa_setting = parent_doc.get('mpesa_setting')
    mode_of_payment = frappe.db.get_value("Mode of Payment", f"Mpesa-{mpesa_setting}", "name")

    current_user = frappe.session.user
    frappe.set_user("Administrator")

    try:
        references = [{
            'reference_doctype': child_doc.reference_doctype,
            'reference_name': child_doc.record,
            'allocated_amount': child_doc.amount
        }]

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
            submit=0,
            references=references,
            party_account=party_account
        )

    except Exception as e:

        frappe.log_error("Error Creating Payment Entry", str(e))
    
    finally:
        frappe.set_user(current_user)