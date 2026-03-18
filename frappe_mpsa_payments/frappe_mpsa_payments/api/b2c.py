import frappe

from frappe_mpsa_payments.services.b2c_request_service import create_b2c_request
from frappe_mpsa_payments.services.b2c_response_service import process_b2c_result


@frappe.whitelist()
def make_b2c_payment_request(doc_name: str) -> dict:
    """
    Queues and initiates a B2C payment request by creating the
    B2C Request document and delegating to the appropriate connector.
    """
    return create_b2c_request(doc_name)


@frappe.whitelist(allow_guest=True)
def b2c_results_callback(**kwargs):
    """
    Handle the B2C callback from Daraja.
    """

    try:
        frappe.log_error(
            "B2C Callback Received",
            f"Received B2C callback with payload: {kwargs}",
        )
        result_payload = kwargs.get("Result") or {}
        process_b2c_result(None, result_payload)
        return "OK"

    except Exception:
        frappe.log_error(frappe.get_traceback(), "B2C Callback Error")
        raise
