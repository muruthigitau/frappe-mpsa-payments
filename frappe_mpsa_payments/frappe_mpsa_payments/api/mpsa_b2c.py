import json
import requests
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse


import frappe
import erpnext
from frappe import _
from frappe.model.document import Document
from frappe.integrations.utils import create_request_log
from frappe.utils import get_url, nowdate, get_datetime
from frappe.utils.password import get_decrypted_password

from .payment_entry import create_payment_entry
from .mpesa_response_handler import b2c_request_on_success, b2c_request_on_error
from .process_request import process_request
from .loan_disbursement import create_loan_disbursement
from ...utils.doctype_names import MPESA_B2C_REQUEST_DOCTYPE, MPESA_SETTINGS_DOCTYPE
from ...utils.definitions import B2CRequestDefinition
from ...utils.utils import build_callback_url
from ...utils.helpers import _get_result_param, update_b2c_reference_status
from ..connectors.connectors import MpesaConnector, update_integration_request


def make_b2c_payment_request(request_data: B2CRequestDefinition, doctype: str, document_name: str, mpesa_settings: str) -> dict:
    """Make a B2C Payment Request."""

    try:

        base_url = get_url()
        callback_url = f"{base_url}/api/method/frappe_mpsa_payments.frappe_mpsa_payments.api.mpsa_b2c.b2c_results_callback"
        mpesa_settings = frappe.get_doc(MPESA_SETTINGS_DOCTYPE, mpesa_settings)

        payload = {
            **request_data.to_dict(), 
            "QueueTimeOutURL": callback_url,
            "ResultURL": callback_url,
        }

        endpoint="mpesa/b2c/v3/paymentrequest"

        response = process_request(
            endpoint=endpoint,
            method="POST",
            payload=payload,
            success_callback=b2c_request_on_success,
            error_callback=b2c_request_on_error,
            request_description="Mpesa B2C",
            doctype=doctype,
            document_name=document_name,
            settings_name=mpesa_settings.name
        )

        return response
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Mpesa B2C Error")
        frappe.log_error(_("Failed to generate Mpesa B2C request. Please check the error logs."))


@frappe.whitelist(allow_guest=True)
def b2c_results_callback(**kwargs):
    """Handle the B2C callback from MPesa API."""
    try:
        result = frappe._dict(kwargs.get("Result", {}))
        originator_conversation_id = result.get("OriginatorConversationID")
        result_code = result.get("ResultCode")
        result_desc = result.get("ResultDesc")
        transaction_id = result.get("TransactionID")
        conversation_id = result.get("ConversationID")

        result_parameters = result.get("ResultParameters", {}).get("ResultParameter", [])
        result_dict = {param["Key"]: param["Value"] for param in result_parameters}

        fields = {
            "status": "Paid" if str(result_code) == "0" else "Failed",
            "result_code": result_code,
            "result_desc": result_desc,
            "conversation_id": conversation_id,
            "originator_conversation_id": originator_conversation_id,
            "transaction_id": transaction_id,
            "recipient_is_registered_customer": result_dict.get("B2CRecipientIsRegisteredCustomer"),
            "charges_paid_acct_avlbl_funds": result_dict.get("B2CChargesPaidAccountAvailableFunds"),
            "receiver_public_name": result_dict.get("ReceiverPartyPublicName"),
            "transaction_completed_datetime": get_datetime(result_dict.get("TransactionCompletedDateTime"))
                if result_dict.get("TransactionCompletedDateTime") else None,
            "utility_acct_avlbl_funds": result_dict.get("B2CUtilityAccountAvailableFunds"),
            "working_acct_avlbl_funds": result_dict.get("B2CWorkingAccountAvailableFunds"),
        }

        request_doc = frappe.get_doc(
            MPESA_B2C_REQUEST_DOCTYPE,
            {"originator_conversation_id": originator_conversation_id}
        )

        for key, value in fields.items():
            if value is not None:
                setattr(request_doc, key, value)
        
        try:
            request_doc.save(ignore_permissions=True)
        except frappe.UniqueValidationError:
            frappe.db.set_value(MPESA_B2C_REQUEST_DOCTYPE, request_doc.name, {
                "status": "Failed"
            })
            frappe.log_error(frappe.get_traceback(), f"Duplicate transaction_id for B2C Request {request_doc.name}")

        # update_b2c_reference_status(request_doc)
        frappe.enqueue(
            "frappe_mpsa_payments.utils.helpers.update_b2c_reference_status",
            queue="short",
            timeout=300,
            b2c_request_doc=request_doc.name
        )

        frappe.log(f"B2C Request updated for {request_doc.name}")
        frappe.publish_realtime(
            event="refresh_form",
            doctype=MPESA_B2C_REQUEST_DOCTYPE,
            docname=request_doc.name
        )

        if str(result_code) == "0":
            b2c_disbursement = frappe.get_doc("B2C Payment Disbursement", request_doc.b2c_payment)
            b2c_disbursement_ref = frappe.get_doc("B2C Payment Disbursement Reference", request_doc.b2c_payment_reference)

            frappe.enqueue(
                "frappe_mpsa_payments.frappe_mpsa_payments.api.mpsa_b2c.handle_successful_payment",
                queue="long",
                timeout=600,
                b2c_disbursement=b2c_disbursement,
                b2c_disbursement_ref=b2c_disbursement_ref
            )

    except Exception:
        frappe.log_error(frappe.get_traceback(), f"B2C Request Callback Error for ID {originator_conversation_id}")
        raise

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
            "reference_type": "Payroll Entry",
            "reference_name": b2c_disbursement_ref.payroll_entry
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
            reference_date=b2c_disbursement_ref.reference_date,
            reference_no=b2c_disbursement_ref.reference_no,
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
