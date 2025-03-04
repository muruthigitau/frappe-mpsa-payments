
from __future__ import unicode_literals
import frappe, requests
from frappe import _
from requests.auth import HTTPBasicAuth
from frappe.utils.response import json_handler
import json
from ..doctype.mpesa_settings.mpesa_settings import (
    get_completed_integration_requests_info,
    fetch_param_value,
    
)

from json import dumps, loads


def get_token(app_key, app_secret, base_url):
    authenticate_uri = "/oauth/v1/generate?grant_type=client_credentials"
    authenticate_url = "{0}{1}".format(base_url, authenticate_uri)

    r = requests.get(authenticate_url, auth=HTTPBasicAuth(app_key, app_secret))

    return r.json()["access_token"]


@frappe.whitelist(allow_guest=True)
def confirmation(**kwargs):
    try:
        args = frappe._dict(kwargs)
        doc = frappe.new_doc("Mpesa C2B Payment Register")
        doc.transactiontype = args.get("TransactionType")
        doc.transid = args.get("TransID")
        doc.transtime = args.get("TransTime")
        doc.transamount = args.get("TransAmount")
        doc.businessshortcode = args.get("BusinessShortCode")
        doc.billrefnumber = args.get("BillRefNumber")
        doc.invoicenumber = args.get("InvoiceNumber")
        doc.orgaccountbalance = args.get("OrgAccountBalance")
        doc.thirdpartytransid = args.get("ThirdPartyTransID")
        doc.msisdn = args.get("MSISDN")
        doc.firstname = args.get("FirstName")
        doc.middlename = args.get("MiddleName")
        doc.lastname = args.get("LastName")
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        context = {"ResultCode": 0, "ResultDesc": "Accepted"}
        return dict(context)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), str(e)[:140])
        context = {"ResultCode": 1, "ResultDesc": "Rejected"}
        return dict(context)


@frappe.whitelist(allow_guest=True)
def validation(**kwargs):
    context = {"ResultCode": 0, "ResultDesc": "Accepted"}
    return dict(context)


@frappe.whitelist()
def get_mpesa_mode_of_payment(company):
    modes = frappe.get_all(
        "Mpesa C2B Payment Register URL",
        filters={"company": company, "register_status": "Success"},
        fields=["mode_of_payment"],
    )
    modes_of_payment = []
    for mode in modes:
        if mode.mode_of_payment not in modes_of_payment:
            modes_of_payment.append(mode.mode_of_payment)
    return modes_of_payment

@frappe.whitelist(allow_guest=True)
def get_mpesa_draft_c2b_payments(
    company,
    full_name=None,
    mode_of_payment=None,
    from_date=None,
    to_date=None,
):
    fields = [
        "name",
        "transid",
        "company",
        "msisdn",
        "full_name",
        "posting_date",
        "posting_time",
        "transamount",
    ]

    filters = {"company": company, "docstatus": 0}
    order_by="posting_date desc, posting_time desc"

    if mode_of_payment:
        filters["mode_of_payment"] = mode_of_payment

    if full_name:
        filters["full_name"] = ["like", f"%{full_name}%"]

    if from_date and to_date:
        filters["posting_date"] = ["between", [from_date, to_date]]
    elif from_date:
        filters["posting_date"] = [">=", from_date]
    elif to_date:
        filters["posting_date"] = ["<=", to_date]

    payments = frappe.get_all(
        "Mpesa C2B Payment Register", 
        filters=filters, fields=fields,order_by=order_by
    )
    
    return payments
    
@frappe.whitelist(allow_guest=True)
def get_draft_pos_invoice(search_term=None):
    from frappe.query_builder import DocType
    from frappe.query_builder.functions import Concat
    from frappe import qb

    SalesInvoice = DocType("Sales Invoice")
    fields = ["*"]
    status_filters = ["Overdue", "Partially Paid", "Unpaid", "Overdue and Discounted", "Partially Paid and Discounted"]

    # Create the base query
    query = (
        qb.from_(SalesInvoice)
        .select(*fields)
        .where(SalesInvoice.docstatus == 1)
        .where(SalesInvoice.status.isin(status_filters))
        .orderby(SalesInvoice.posting_date, order=qb.desc)
    )

    if search_term:
        search_filter = (
            (SalesInvoice.customer.like(f"%{search_term}%")) |
            (SalesInvoice.name.like(f"%{search_term}%"))
        )
        query = query.where(search_filter)

    invoices = query.run(as_dict=True)

    frappe.response['message'] = invoices

@frappe.whitelist()
def submit_mpesa_payment(mpesa_payment, customer):
    try:
        doc = process_mpesa_payment(mpesa_payment, customer, submit_payment=True)
        return frappe.get_doc("Payment Entry", doc.payment_entry)
    except Exception as e:
        frappe.log_error(f"Error: {str(e)}", "submit_mpesa_payment")
        raise

@frappe.whitelist()
def submit_instant_mpesa_payment():
    mpesa_payment = frappe.form_dict.get("mpesa_payment")
    customer = frappe.form_dict.get("customer")
    # pos_profile = frappe.form_dict.get("pos_profile")
    # mode_of_payment = get_payment_method(pos_profile)

    try:
        process_mpesa_payment(mpesa_payment, customer, submit_payment=False)
    except Exception as e:
        frappe.log_error(f"Error: {str(e)}", "submit_instant_mpesa_payment")
        raise

def process_mpesa_payment(mpesa_payment, customer, submit_payment=False):
    try:
        doc = frappe.get_doc("Mpesa C2B Payment Register", mpesa_payment)
        doc.customer = customer
        # doc.mode_of_payment = mode_of_payment
        #TODO: after testing, mode of payment
        doc.mode_of_payment = get_mode_of_payment(doc)
        doc.submit_payment=submit_payment
        doc.save()
        doc.submit()
        frappe.db.commit()  

        doc.reload()  

        return doc
    except Exception as e:
        frappe.log_error(f"Error: {str(e)}", "process_mpesa_payment")
        raise

def get_payment_method(pos_profile):
    pos_profile_doc = frappe.get_doc("POS Profile", pos_profile)
    for payment in pos_profile_doc.payments:
        if payment.default == 1:
            return payment.mode_of_payment
    return None

def get_mode_of_payment(mpesa_doc):
    business_short_code=mpesa_doc.businessshortcode
    mode_of_payment = frappe.get_value("Mpesa C2B Payment Register URL", {"business_shortcode": business_short_code, "register_status": "Success"}, "mode_of_payment")
    if mode_of_payment is None:
        mode_of_payment = frappe.get_value("Mpesa C2B Payment Register URL", {"till_number": business_short_code, "register_status": "Success"}, "mode_of_payment")
    return mode_of_payment
    
@frappe.whitelist(allow_guest=True)
def handle_transaction_status_result():
    """Handle the transaction status response from Mpesa"""
    try:
        response = frappe.request.data
        response_data = json.loads(response)

        integration_request = frappe.get_doc({
            "doctype": "Integration Request",
            "is_remote_request": 1,
            "integration_request_service": "Mpesa Transaction Status Result Callback",
            "reference_doctype": "Mpesa C2B Payment Register",
            "status": "Queued",
            "data": json.dumps(response_data),
            "url": frappe.request.url,
            "method": "POST"
        }).insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.enqueue(
            "frappe_mpsa_payments.frappe_mpsa_payments.api.m_pesa_api.process_mpesa_integration_request",
            queue="short",
            timeout=300,
            job_id=f"mpesa_process_{integration_request.name}",
            integration_request_name=integration_request.name,
            deduplicate=True
        )

        return {"status": "queued", "message": "Transaction queued for processing"}
    
    except json.JSONDecodeError as e:
        frappe.log_error(f"Failed to decode JSON from Mpesa response: {str(e)}", "Mpesa API Error")
        return {"status": "error", "message": "Invalid JSON data"}
    except Exception as e:
        frappe.log_error(f"Error in Mpesa webhook: {str(e)}", "Mpesa API Error")
        return {"status": "error", "message": f"Webhook error: {str(e)}"}
         

def process_mpesa_integration_request(integration_request_name):
    """Process the Mpesa Integration Request and publish updates in real-time"""
    try:
        # Fetch the Integration Request
        integration_request = frappe.get_doc("Integration Request", integration_request_name)
        
        # Parse the stored data
        response_data = json.loads(integration_request.data)
        result_data = response_data.get("Result", {})
        result_parameters = result_data.get("ResultParameters", {}).get("ResultParameter", [])
        result_params = {param.get("Key", ""): param.get("Value", "") for param in result_parameters if "Key" in param}
        
        result_code = result_data.get("ResultCode", None)
        receipt_no = result_params.get("ReceiptNo", "")
        business_shortcode = result_params.get("CreditPartyName", "").split("-")

        if result_code == 0:
            if frappe.db.exists("Mpesa C2B Payment Register", {"transid": receipt_no}):
                error_msg = f"Duplicate transaction: Receipt No {receipt_no} already exists"
                integration_request.status = "Failed"
                integration_request.output = error_msg
                integration_request.save(ignore_permissions=True)
                frappe.db.commit()
                
                frappe.publish_realtime(
                    event="mpesa_transaction_status",
                    message={"status": "error", "message": error_msg},
                    user=frappe.session.user
                )
                return
            
            # Create the Mpesa document
            mpesa_doc = frappe.new_doc("Mpesa C2B Payment Register")
            mpesa_doc.full_name = result_params.get("DebitPartyName", "")
            mpesa_doc.transactiontype = result_params.get("ReasonType", "")
            mpesa_doc.transid = result_params.get("ReceiptNo", "")
            mpesa_doc.transtime = result_params.get("InitiatedTime", "")
            mpesa_doc.transamount = float(result_params.get("Amount", 0.0))
            mpesa_doc.businessshortcode = business_shortcode[0]
            mpesa_doc.billrefnumber = result_params.get("ReceiptNo", "")
            mpesa_doc.invoicenumber = result_params.get("TransactionID", "")
            mpesa_doc.orgaccountbalance = result_params.get("DebitAccountType", "")
            mpesa_doc.thirdpartytransid = result_params.get("OriginatorConversationID", "")

            debit_party = result_params.get("DebitPartyName", "").split(" - ")
            mpesa_doc.msisdn = debit_party[0] if len(debit_party) > 0 else ""
            name_parts = debit_party[1].split(" ") if len(debit_party) > 1 else ["", "", ""]
            mpesa_doc.firstname = name_parts[0]
            mpesa_doc.middlename = name_parts[1] if len(name_parts) > 1 else ""
            mpesa_doc.lastname = name_parts[-1] if len(name_parts) > 2 else ""

            mpesa_doc.insert(ignore_permissions=True)
            frappe.db.commit()

            success_msg = "Transaction processed successfully"
            integration_request.status = "Completed"
            integration_request.output = success_msg
            integration_request.reference_document = mpesa_doc.name
            integration_request.save(ignore_permissions=True)
            frappe.db.commit()

            frappe.publish_realtime(
                event="mpesa_transaction_status",
                message={"status": "success", "message": success_msg, "doc_name": mpesa_doc.name},
                user=frappe.session.user
            )
        
        else:
            error_msg = "Transaction failed with non-zero result code"
            integration_request.status = "Failed"
            integration_request.output = error_msg
            integration_request.save(ignore_permissions=True)
            frappe.db.commit()

            frappe.publish_realtime(
                event="mpesa_transaction_status",
                message={"status": "error", "message": error_msg},
                user=frappe.session.user
            )

    except Exception as e:
        error_message = f"Mpesa Processing Error: {str(e)}"
        integration_request.status = "Failed"
        integration_request.output = error_message
        integration_request.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.log_error(f"{error_message}\nData: {integration_request.data}", "Mpesa Integration Error")
        frappe.publish_realtime(
            event="mpesa_transaction_status",
            message={"status": "error", "message": error_message},
            user=frappe.session.user
        )


@frappe.whitelist(allow_guest=True)
def handle_queue_timeout():
    """Handle the timeout response from Mpesa."""
    try:
        response = frappe.request.data
        response_data = json.loads(response)

        frappe.log_error(
            title="Mpesa Queue Timeout",
            message=f"Timeout response received: {frappe.as_json(response_data)}"
        )

        return {"status": "timeout", "message": "Timeout response logged successfully."}

    except json.JSONDecodeError:
        frappe.log_error(
            title="Mpesa Timeout Error",
            message="Failed to decode JSON from timeout response."
        )
        return {"status": "error", "message": "Invalid JSON received."}

    except Exception as e:
        error_message = f"Mpesa Timeout Error: {str(e)}"
        frappe.log_error(
            title="Mpesa Timeout Error",
            message=error_message
        )
        return {"status": "error", "message": str(e)}

@frappe.whitelist(allow_guest=True)
def verify_transaction(**kwargs) -> None:
    """Verify the transaction result received via callback from stk."""
    
    transaction_response = frappe._dict(kwargs["Body"]["stkCallback"])

    checkout_id = getattr(transaction_response, "CheckoutRequestID", "")
    if not isinstance(checkout_id, str):
        frappe.throw(_("Invalid Checkout Request ID"))
    print("=====================================")
    print(str(transaction_response))
    integration_request = frappe.get_doc("Integration Request", checkout_id)
    transaction_data = frappe._dict(loads(integration_request.data))
    total_paid = 0  
    success = False  # for reporting successfull callback to point of sale ui

    if transaction_response["ResultCode"] == 0:
        if (
            integration_request.reference_doctype
            and integration_request.reference_docname
        ):
            try:
                item_response = transaction_response["CallbackMetadata"]["Item"]
                amount = fetch_param_value(item_response, "Amount", "Name")
                mpesa_receipt = fetch_param_value(
                    item_response, "MpesaReceiptNumber", "Name"
                )
                pr = frappe.get_doc(
                    integration_request.reference_doctype,
                    integration_request.reference_docname,
                )

                mpesa_receipts, completed_payments = (
                    get_completed_integration_requests_info(
                        integration_request.reference_doctype,
                        integration_request.reference_docname,
                        checkout_id,
                    )
                )

                total_paid = amount + sum(completed_payments)
                mpesa_receipts = ", ".join(mpesa_receipts + [mpesa_receipt])

                if total_paid >= pr.grand_total:
                    pr.run_method("on_payment_authorized", "Completed")
                    success = True

                frappe.db.set_value(
                    "POS Invoice",
                    pr.reference_name,
                    "mpesa_receipt_number",
                    mpesa_receipts,
                )
                integration_request.handle_success(transaction_response)
            except Exception:
                integration_request.handle_failure(transaction_response)
                frappe.log_error("Mpesa: Failed to verify transaction")

    else:
        integration_request.handle_failure(transaction_response)

    frappe.publish_realtime(
        event="process_phone_payment",
        doctype="POS Invoice",
        docname=transaction_data.payment_reference,
        user=integration_request.owner,
        message={
            "amount": total_paid,
            "success": success,
            "failure_message": (
                transaction_response["ResultDesc"]
                if transaction_response["ResultCode"] != 0
                else ""
            ),
        },
    )
