import json
import requests
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse


import frappe
import erpnext
from frappe.model.document import Document
from frappe.integrations.utils import create_request_log
from frappe.utils import get_request_site_address, nowdate, get_datetime
from frappe.utils.password import get_decrypted_password

from .payment_entry import create_payment_entry
from .loan_disbursement import create_loan_disbursement
from ...utils.definitions import B2CRequestDefinition
from ..connectors.connectors import MpesaConnector, update_integration_request


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

            except requests.Timeout as e:
                update_integration_request(
                    self.integration_request.name,
                    status="Failed",
                    error="Timeout: Remote server did not respond in time."
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
    result_parameters = result.get("ResultParameters", {}).get("ResultParameter", [])
    result_dict = {param["Key"]: param["Value"] for param in result_parameters}
    
    result_json = json.dumps(result)

    try:
        b2c_payment_disbursement_reference = frappe.get_doc("B2C Payment Disbursement Reference", {"originator_conversation_id": originator_conversation_id})
        b2c_payment_disbursement = frappe.get_doc(b2c_payment_disbursement_reference.parenttype, b2c_payment_disbursement_reference.parent)

        if result.get("ResultCode") != 0:
            frappe.db.set_value("B2C Payment Disbursement Reference", b2c_payment_disbursement_reference, "payment_status", "Failed")
            
            update_integration_request(
                originator_conversation_id,
                "Failed",
                output=result_json,
                error=result.get("ResultDesc") or result.get("errorMessage"),
            )
            frappe.log_error(f"B2C Request failed: {result.ResultDesc}", "Mpesa B2C Error")

            publish_b2c_payment_update(b2c_payment_disbursement.name, b2c_payment_disbursement_reference.idx, b2c_payment_disbursement_reference.party, b2c_payment_disbursement_reference.allocated_amount, "Failed")

        else:
            create_mpesa_transaction_entry(result, b2c_payment_disbursement, b2c_payment_disbursement_reference)

            frappe.db.set_value(
                "B2C Payment Disbursement Reference", 
                b2c_payment_disbursement_reference, 
                {
                    "reference_no": f"{result_dict.get("TransactionReceipt")}",
                    "reference_date": f"{get_datetime(result_dict.get("TransactionCompletedDateTime"))}",
                    "payment_status": "Paid"
                }
            )
            
            update_integration_request(
                originator_conversation_id,
                "Completed",
                output=result_json,
            )

            publish_b2c_payment_update(b2c_payment_disbursement.name, b2c_payment_disbursement_reference.idx, b2c_payment_disbursement_reference.party, b2c_payment_disbursement_reference.allocated_amount, "Paid")

            frappe.enqueue(
                "frappe_mpsa_payments.frappe_mpsa_payments.api.mpsa_b2c.handle_successful_payment",
                queue="long",
                timeout=600,
                b2c_disbursement=b2c_payment_disbursement,
                b2c_disbursement_ref=b2c_payment_disbursement_reference
            )

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Failed to update payment_status in callback")

    return "Success"


def handle_successful_payment(b2c_disbursement, b2c_disbursement_ref):
    """
    Trigger follow-up accounting entries based on reference doctype.
    This function will be enqueued and run in the background.
    """

    try:
        match b2c_disbursement_ref.reference_doctype:
            case "Salary Slip":
                create_journal_entry(b2c_disbursement, b2c_disbursement_ref)
            case "Employee Advance" | "Expense Claim" | "Purchase Invoice" | "Purchase Order":
                create_payment_entry_for_doc(b2c_disbursement, b2c_disbursement_ref)
            case "Loan":
                create_loan_disbursement(b2c_disbursement, b2c_disbursement_ref)
            case _:
                frappe.log_error(
                    f"Unsupported reference_doctype: {b2c_disbursement_ref.reference_doctype}",
                    "Payment Callback Handler"
                )
    except Exception as e:
        error_msg = f"Error handling payment for {b2c_disbursement_ref.name}: {str(e)}"
        frappe.log_error(frappe.get_traceback(), "B2C Payment Disbursement Reference")

def create_mpesa_transaction_entry(result: dict, b2c_disbursement: Document, b2c_disbursement_ref: Document):
    """
    Store a successful B2C transaction callback into MPesa B2C Payments Transactions.
    :param result: Dictionary parsed from Safaricom's B2C callback (Success).
    :param b2c_disbursement: The parent B2C Payment Disbursement document.
    :param b2c_disbursement_ref: The item/transaction with a successful response.
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

        if frappe.db.exists("MPesa B2C Payments Transactions", transaction_id):
            frappe.throw(f"Transaction with ID {transaction_id} already exists.")

        doc = frappe.new_doc("MPesa B2C Payments Transactions")
        doc.b2c_payment_name = b2c_disbursement.name
        doc.b2c_payment_item_name = b2c_disbursement_ref.name
        doc.transaction_id = transaction_id
        doc.transaction_amount = transaction_amount
        doc.receiver_public_name = receiver_public_name
        doc.recipient_is_registered_customer = recipient_is_registered_customer
        doc.charges_paid_acct_avlbl_funds = charges_paid
        doc.working_acct_avlbl_funds = working_acct_avlbl_funds
        doc.utility_acct_avlbl_funds = utility_funds
        doc.transaction_completed_datetime = get_datetime(transaction_completed_datetime)
        doc.account_paid_from = b2c_disbursement.paid_to
        doc.account_paid_to = b2c_disbursement.paid_to

        doc.insert(ignore_permissions=True)
        frappe.db.commit()

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "B2C Payment Transaction Save Failed")

def create_journal_entry(b2c_disbursement, b2c_disbursement_ref):
    """ Create Journal Entry for Salary Slip after successful B2C payment."""

    try:
        salary_slip = frappe.get_doc("Salary Slip", b2c_disbursement_ref.reference_name)
        if not salary_slip:
            frappe.log_error(f"Salary slip {salary_slip.name} not found")

        if not b2c_disbursement.paid_from:
            frappe.throw("Paid From account not is set in B2C Payment Disbursement")
        if not b2c_disbursement.paid_to:
            frappe.log_error(f"Paid To Account is not set in B2C Payment Disbursement")

        journal_entry = frappe.new_doc("Journal Entry")
        journal_entry.voucher_type = "Bank Entry"
        journal_entry.posting_date = nowdate()
        journal_entry.company = b2c_disbursement.company
        journal_entry.user_remark = f"B2C Payment Disbursed for Salary Slip {salary_slip.name}"

        journal_entry.append("accounts", {
            "account": b2c_disbursement.paid_from,
            "credit_in_account_currency": b2c_disbursement_ref.allocated_amount
        })

        journal_entry.append("accounts", {
            "account": b2c_disbursement.paid_to,
            "debit_in_account_currency": b2c_disbursement_ref.allocated_amount,
            "party_type": b2c_disbursement_ref.party_type,
            "party": b2c_disbursement_ref.party,
        })

        journal_entry.insert(ignore_permissions=True)
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to create Journal Entry")

def create_payment_entry_for_doc(b2c_disbursement, b2c_disbursement_ref):
    party_type = b2c_disbursement_ref.party_type
    party_account = b2c_disbursement.paid_to
    party = frappe.db.get_value(party_type, b2c_disbursement_ref.party, "name")
    amount = b2c_disbursement_ref.allocated_amount

    company = b2c_disbursement.company
    currency = frappe.db.get_value('Company', company, 'default_currency')

    mode_of_payment = b2c_disbursement.mode_of_payment

    current_user = frappe.session.user
    frappe.set_user("Administrator")

    try:
        references = [{
            'reference_doctype': b2c_disbursement_ref.reference_doctype,
            'reference_name': b2c_disbursement_ref.reference_name,
            'allocated_amount': b2c_disbursement_ref.allocated_amount
        }]

        payment_entry = create_payment_entry(
            company,
            party,
            amount,
            currency,
            mode_of_payment,
            party_type=party_type,
            reference_date=nowdate(),
            reference_no=b2c_disbursement_ref.originator_conversation_id,
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

def publish_b2c_payment_update(
    payment_docname: str, 
    row_number: int, 
    party: str,
    allocated_amount: float,
    status: str,
    ):
    """Broadcast B2C payment status update to the client side via real-time event."""       
    frappe.publish_realtime(
        "b2c_payment_update",
        {
            "docname": payment_docname,
            "row_number": row_number,
            "party": party,
            "amount": allocated_amount,
            "status": status,
        }
    )
