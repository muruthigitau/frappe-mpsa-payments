import frappe
from frappe.utils import getdate

from frappe_mpsa_payments.connectors.factory import get_b2c_connector
from frappe_mpsa_payments.utils.doctype_names import B2C_REQUEST_DOCTYPE


def process_b2c_result(provider: str, payload: dict) -> None:
    """
    Handle the raw B2C callback payload:
    1) Instantiate connector via factory.
    2) Delegate to its handle_callback(), which updates the request doc
       and enqueues downstream work.
    """
    frappe.local.flags.ignore_permissions = True

    try:
        originator_id = payload.get("OriginatorConversationID")
        req = frappe.get_doc(
            B2C_REQUEST_DOCTYPE,
            {"originator_conversation_id": originator_id},
            ignore_permissions=True,
        )

    finally:
        frappe.local.flags.ignore_permissions = False

        # Figure out which settings doc to use
        if req.mpesa_settings:
            provider = "Mpesa"
            settings_name = req.mpesa_settings
        elif req.stanbic_settings:
            provider = "Stanbic"
            settings_name = req.stanbic_settings

    # Now load the connector with a real settings_name
    
    connector = get_b2c_connector(provider, settings_name)
    connector.handle_callback(payload)


def update_b2c_reference_status(b2c_request_name: str, enqueue_next: bool = False):
    """
    After a B2C Request finishes, update the matching Reference row,
    then (optionally) enqueue the post-processing job.
    """
    req = frappe.get_doc(B2C_REQUEST_DOCTYPE, b2c_request_name)
    ref_name = req.b2c_payment_disbursement_reference

    if req.status in ("Paid", "Failed") and ref_name:
        update = {
            "Paid": {
                "payment_status": "Paid",
                "reference_no": req.transaction_id,
                "reference_date": getdate(req.transaction_completed_datetime),
            },
            "Failed": {"payment_status": "Failed"},
        }[req.status]

        frappe.db.set_value("B2C Payment Disbursement Reference", ref_name, update)
        frappe.db.commit()

    if enqueue_next and req.status == "Paid":
        from frappe_mpsa_payments.services.b2c_postprocess_service import (
            handle_successful_payment,
        )

        handle_successful_payment(req.b2c_payment_disbursement, ref_name)
