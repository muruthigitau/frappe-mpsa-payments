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