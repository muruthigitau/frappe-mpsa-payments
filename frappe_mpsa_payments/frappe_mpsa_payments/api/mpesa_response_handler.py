import frappe
from frappe.utils import now_datetime

from ...utils.doctype_names import (
    MPESA_EXPRESS_REQUEST_DOCTYPE,
    TAX_REMMITANCE_DOCTYPE,
)
from ...utils.utils import (
    handle_successful_transaction,
    log_and_throw_error,
    update_mpesa_request_status,
)


def balance_query_on_success(response: dict, document_name: str, **kwargs) -> None:
    pass


def transaction_status_on_success(response: dict, document_name: str, **kwargs) -> None:
    try:
        # frappe.set_user("Administrator")

        frappe.flags.ignore_permissions = True

        result_code = response.get("ResultCode")
        status = "Completed" if result_code == "0" else "Failed"

        request_doc = frappe.get_doc(MPESA_EXPRESS_REQUEST_DOCTYPE, document_name)

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
        request_doc.reconcile_payment()

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


def stk_push_on_error(
    response: dict, payload: dict, document_name: str, **kwargs
) -> None:
    try:
        frappe.db.set_value(
            MPESA_EXPRESS_REQUEST_DOCTYPE,
            document_name,
            {
                # "response_code": response.get("errorCode", ""),
                "response_description": response.get("errorMessage", ""),
                "status": "Failed",
            },
        )
        frappe.db.commit()

    except Exception:
        frappe.log_error(frappe.get_traceback(), f"STK Push Error for {document_name}")
        raise


def tax_remmitance_on_success(
    response: dict, payload: dict, document_name: str, **kwargs
) -> None:
    try:
        fields = {
            "conversation_id": response.get("ConversationID", ""),
            "response_code": response.get("ResponseCode", ""),
            "response_description": response.get("ResponseDescription", ""),
            "amount": payload.get("Amount", 0.0),
            "status": "Completed" if response.get("ResponseCode") == "0" else "Failed",
        }

        doctype = kwargs.get("doctype", "")

        if doctype == TAX_REMMITANCE_DOCTYPE:
            for key, value in fields.items():
                frappe.db.set_value(TAX_REMMITANCE_DOCTYPE, document_name, key, value)
        else:
            doc = frappe.new_doc(TAX_REMMITANCE_DOCTYPE)
            for key, value in fields.items():
                setattr(doc, key, value)
            doc.insert(ignore_permissions=True)
            frappe.logger().info(
                f"Mpesa Tax Remittance created for {document_name} with ID {doc.name}"
            )

        frappe.db.commit()

        frappe.publish_realtime(
            event="refresh_form",
            doctype=TAX_REMMITANCE_DOCTYPE,
            docname=document_name,
        )

    except Exception:
        frappe.log_error(
            frappe.get_traceback(), f"Tax Remittance Success Error for {document_name}"
        )
        raise


def tax_remmitance_on_error(
    response: dict, payload: dict, document_name: str, **kwargs
) -> None:
    try:
        frappe.db.set_value(
            TAX_REMMITANCE_DOCTYPE,
            document_name,
            {
                # "response_code": response.get("errorCode", ""),
                "response_description": response.get("errorMessage", ""),
                "status": "Failed",
            },
        )
        frappe.db.commit()

    except Exception:
        frappe.log_error(
            frappe.get_traceback(), f"Tax Remittance Error for {document_name}"
        )
        raise


# {
#     "OriginatorConversationID": "b331-459a-8a17-c0c7053a27ab12560",
#     "ConversationID": "AG_20260219_010020060obc9af6zk5v",
#     "ResponseCode": "0",
#     "ResponseDescription": "Accept the service request successfully.",
# }
