from ...utils.doctype_names import MPESA_EXPRESS_REQUEST_DOCTYPE, MPESA_SETTINGS_DOCTYPE
import frappe
from frappe.utils import now_datetime



def balance_query_on_success(response: dict, document_name: str, **kwargs) -> None:
    pass
        
        
def transaction_status_on_success(response: dict, document_name: str, **kwargs) -> None:
    try:
        result_code = response.get("ResultCode")
        result_desc = response.get("ResultDesc")
        merchant_request_id = response.get("MerchantRequestID")
        checkout_request_id = response.get("CheckoutRequestID")
        response_code = response.get("ResponseCode")
        response_description = response.get("ResponseDescription")
        status = "Completed" if result_code == "0" else "Failed"

        # Fetch the current status from the database
        request_doc = frappe.get_doc(MPESA_EXPRESS_REQUEST_DOCTYPE, document_name)

        # Only proceed if the new status is "Completed" and it's a change from the current status
        if status == "Completed" and request_doc.status != "Completed" and request_doc.reference_doctype == "Payment Request":
            payment_entry = frappe.get_doc("Payment Request", request_doc.reference_name)
            try:
                payment_entry.create_payment_entry()
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Payment Entry Creation Error: {document_name}")
                
            if request_doc.reference_doctype == "Sales Order":
                payment_entry.make_invoice()
            frappe.db.set_value("Payment Request", payment_entry.name, "status", "Paid")

        # Update the database record
        frappe.db.set_value(MPESA_EXPRESS_REQUEST_DOCTYPE, document_name, {
            "result_code": result_code,
            "result_desc": result_desc,
            "merchant_request_id": merchant_request_id,
            "checkout_request_id": checkout_request_id,
            "response_code": response_code,
            "response_description": response_description,
            "status": status
        })

        # Publish an event to refresh the form
        frappe.publish_realtime(event='refresh_form', doctype=MPESA_EXPRESS_REQUEST_DOCTYPE, docname=document_name)

    except Exception:
        frappe.log_error(frappe.get_traceback(), f"MPESA Transaction Status Update Error: {document_name}")


def stk_push_on_success(response: dict, payload: dict, document_name: str, **kwargs) -> None:
    try:
        fields = {
            "merchant_request_id": response.get("MerchantRequestID", ""),
            "checkout_request_id": response.get("CheckoutRequestID", ""),
            "response_code": response.get("ResponseCode", ""),
            "response_description": response.get("ResponseDescription", ""),
            "result_code": response.get("ResultCode", ""),
            "result_desc": response.get("ResultDesc", ""),
            "amount": payload.get("Amount", 0.0), 
            "phone_number": payload.get("PhoneNumber", ""),
            "account_reference": response.get("AccountReference", ""),
            "transaction_desc": response.get("TransactionDesc", ""),
            "transaction_id": response.get("MpesaReceiptNumber", ""),
            "timestamp": now_datetime(),
            "settings": kwargs.get("settings_name", ""),
        }

        doctype = kwargs.get("doctype", "")

        if doctype == MPESA_EXPRESS_REQUEST_DOCTYPE:
            for key, value in fields.items():
                frappe.db.set_value(MPESA_EXPRESS_REQUEST_DOCTYPE, document_name, key, value)
            frappe.logger().info(f"Mpesa Express Request updated for {document_name}")
        else:
            doc = frappe.new_doc(MPESA_EXPRESS_REQUEST_DOCTYPE)
            for key, value in fields.items():
                setattr(doc, key, value)
            doc.insert(ignore_permissions=True)
            frappe.logger().info(f"Mpesa Express Request created for {document_name} with ID {doc.name}")

        frappe.db.commit()

        frappe.publish_realtime(event='refresh_form', doctype=MPESA_EXPRESS_REQUEST_DOCTYPE, docname=document_name)

        # frappe.enqueue(
        #     "frappe_mpsa_payments.frappe_mpsa_payments.api.m_pesa_api.check_transaction_status",
        #     name=document_name,
        #     enqueue_after_commit=True,
        #     timeout=300
        # )

    except Exception:
        frappe.log_error(frappe.get_traceback(), f"STK Push Success Error for {document_name}")
        raise
