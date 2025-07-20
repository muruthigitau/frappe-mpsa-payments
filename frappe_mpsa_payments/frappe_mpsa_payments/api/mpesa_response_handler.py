import frappe
from frappe.utils import now_datetime

from ...utils.doctype_names import MPESA_EXPRESS_REQUEST_DOCTYPE, MPESA_SETTINGS_DOCTYPE
from ...utils.utils import (
    handle_successful_transaction,
    log_and_throw_error,
    update_mpesa_request_status,
)


def balance_query_on_success(response: dict, document_name: str, **kwargs) -> None:
    pass


def transaction_status_on_success(response: dict, document_name: str, **kwargs) -> None:
    try:
        frappe.set_user("Administrator")

        result_code = response.get("ResultCode")
        status = "Completed" if result_code == "0" else "Failed"
        metadata_dict = kwargs.get("metadata", {})

        request_doc = frappe.get_doc(MPESA_EXPRESS_REQUEST_DOCTYPE, document_name)
        settings = frappe.get_doc(MPESA_SETTINGS_DOCTYPE, request_doc.settings)

        if status == "Completed" and request_doc.status != "Completed":
            handle_successful_transaction(
                request_doc, metadata_dict, settings, response.get("CheckoutRequestID")
            )

        update_mpesa_request_status(
            document_name,
            {
                "result_code": result_code,
                "result_desc": response.get("ResultDesc"),
                "merchant_request_id": response.get("MerchantRequestID"),
                "checkout_request_id": response.get("CheckoutRequestID"),
                "response_code": response.get("ResponseCode"),
                "response_description": response.get("ResponseDescription"),
                "status": status,
            },
        )

    except Exception:
        log_and_throw_error("MPESA Transaction Status Update Error", document_name)


def stk_push_on_success(
    response: dict, payload: dict, document_name: str, **kwargs
) -> None:
    try:
        fields = {
            "merchant_request_id": response.get("MerchantRequestID", ""),
            "checkout_request_id": response.get("CheckoutRequestID", ""),
            "response_code": response.get("ResponseCode", ""),
            "response_description": response.get("ResponseDescription", ""),
            "customer_message": response.get("CustomerMessage", ""),
            "amount": payload.get("Amount", 0.0),
            "phone_number": payload.get("PhoneNumber", ""),
            "timestamp": now_datetime(),
            "settings": kwargs.get("settings_name", ""),
        }

        doctype = kwargs.get("doctype", "")

        if doctype == MPESA_EXPRESS_REQUEST_DOCTYPE:
            for key, value in fields.items():
                frappe.db.set_value(
                    MPESA_EXPRESS_REQUEST_DOCTYPE, document_name, key, value
                )
            frappe.logger().info(f"Mpesa Express Request updated for {document_name}")
        else:
            doc = frappe.new_doc(MPESA_EXPRESS_REQUEST_DOCTYPE)
            for key, value in fields.items():
                setattr(doc, key, value)
            doc.insert(ignore_permissions=True)
            frappe.logger().info(
                f"Mpesa Express Request created for {document_name} with ID {doc.name}"
            )

        frappe.db.commit()

        frappe.publish_realtime(
            event="refresh_form",
            doctype=MPESA_EXPRESS_REQUEST_DOCTYPE,
            docname=document_name,
        )

        # frappe.enqueue(
        #     "frappe_mpsa_payments.frappe_mpsa_payments.api.m_pesa_api.check_transaction_status",
        #     name=document_name,
        #     enqueue_after_commit=True,
        #     timeout=300
        # )

    except Exception:
        frappe.log_error(
            frappe.get_traceback(), f"STK Push Success Error for {document_name}"
        )
        raise
