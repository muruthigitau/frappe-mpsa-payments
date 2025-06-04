from datetime import datetime
from typing import Literal

import frappe

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

def update_disbursement_status(b2c_payment_disbursement: str) -> None:
    """
    Update the B2C Payment Disbursement status based on all its child reference payment statuses.
    Called from a background job to avoid contention and db locks.
    """

    if not b2c_payment_disbursement:
        return

    try:
        disbursement = frappe.get_doc("B2C Payment Disbursement", b2c_payment_disbursement)
        references = frappe.get_all(
            "B2C Payment Disbursement Reference",
            filters={"parent": b2c_payment_disbursement},
            fields=["name", "payment_status"]
        )

        total = len(references)
        paid = sum(1 for ref in references if ref.payment_status == "Paid")
        failed = sum(1 for ref in references if ref.payment_status == "Failed")

        new_status = "Not Initiated"
        if paid == total:
            new_status = "Paid"
        elif failed == total:
            new_status = "Failed"
        elif paid or failed:
            new_status = "Partly Paid"
        elif total > 0:
            new_status = "Initiated"

        frappe.db.set_value("B2C Payment Disbursement", b2c_payment_disbursement, "status", new_status)

    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Error updating B2C Payment Disbursement status for {b2c_payment_disbursement}")