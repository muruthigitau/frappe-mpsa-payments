from datetime import datetime
from typing import Literal

import frappe
from frappe.utils import getdate
from .doctype_names import MPESA_B2C_REQUEST_DOCTYPE

# from .doctype_names import DARAJA_ACCESS_TOKENS_DOCTYPE


# def save_access_token(
#     token: str,
#     expiry_time: str | datetime,
#     fetch_time: str | datetime,
#     associated_setting: str,
#     doctype: str = DARAJA_ACCESS_TOKENS_DOCTYPE,
# ) -> bool:
#     doc = frappe.new_doc(doctype)

#     doc.associated_settings = associated_setting

#     doc.access_token = token
#     doc.expiry_time = expiry_time
#     doc.token_fetch_time = fetch_time

#     try:
#         doc.save(ignore_permissions=True)
#         doc.submit()

#         return True

#     except Exception:
#         # TODO: Not sure what exception is thrown here. Confirm
#         frappe.throw("Error Encountered")
#         return False


def update_integration_request(
    integration_request: str,
    status: Literal["Completed", "Failed"],
    output: str | None = None,
    error: str | None = None,
) -> None:
    doc = frappe.get_doc("Integration Request", integration_request, for_update=True)
    doc.status = status
    doc.error = error
    doc.output = output
    doc.save(ignore_permissions=True)


def _get_result_param(result: dict, key_name: str) -> str:
    """Helper to extract a parameter from ResultParameters array"""
    try:
        parameters = result.get("ResultParameters", {}).get("ResultParameter", [])
        for param in parameters:
            if param.get("key") == key_name:
                return param.get("Value", "")
    
    except Exception:
        pass

    return ""

def update_b2c_reference_status(b2c_request_doc: str) -> None:
    try:
        request_doc = frappe.get_doc(MPESA_B2C_REQUEST_DOCTYPE, b2c_request_doc)

        if request_doc.status in ("Paid", "Failed") and request_doc.b2c_payment_reference:
            update_fields = {
                "Paid": {
                    "payment_status": "Paid",
                    "reference_no": request_doc.transaction_id,
                    "reference_date": getdate(request_doc.transaction_completed_datetime)
                },
                "Failed": {
                    "payment_status": "Failed"
                }
            }.get(request_doc.status)

            frappe.db.set_value(
                "B2C Payment Disbursement Reference",
                request_doc.b2c_payment_reference,
                update_fields
            )

    except frappe.DoesNotExistError:
        frappe.log_error(
            f"Mpesa B2C Payment document '{b2c_request_doc}' not found.",
            "B2C Reference Status Update Error"
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Failed to update B2C Reference status for B2C Payment: {b2c_request_doc}"
        )
        raise
