import frappe
from frappe import _
import json


def get_context(context):
    q = frappe.local.form_dict
    context.redirect_to = q.get("redirect_to")

    mpesa_gateways = get_mpesa_gateways()
    context.mpesa_gateways = mpesa_gateways

    reference_map_raw = get_all_gateway_reference_map(mpesa_gateways)
    context.reference_map_json = json.dumps(reference_map_raw)

    if q.get("id"):
        context.is_new = False
        load_existing(context, q.get("id"))
        frappe.local.form_dict = {"id": q.get("id"), "redirect_to": context.redirect_to}
    else:
        context.is_new = True
        context.mpesa_request = {
            "phone": clean_null(q.get("phone")),
            "payment_gateway": clean_null(q.get("payment_gateway")),
            "reference_type": clean_null(q.get("reference_type")),
            "reference_id": clean_null(q.get("reference_id")),
            "amount": clean_null(q.get("amount")),
        }


def get_mpesa_gateways():
    return frappe.get_all(
        "Payment Gateway",
        filters={"gateway_settings": "Mpesa Settings"},
        fields=["name", "gateway_settings", "gateway_controller"],
        ignore_permissions=True,
    )


def get_all_gateway_reference_map(gateways):
    reference_map = {}
    for gateway in gateways:
        mpesa_settings_name = gateway.get("gateway_controller")
        gateway_name = gateway.get("name")

        if mpesa_settings_name:
            settings = frappe.get_doc(
                "Mpesa Settings", mpesa_settings_name, ignore_permissions=True
            )
            reconciliation_orders = settings.reconciliation_order
            reference_types = [
                order.get("target_doctype") for order in reconciliation_orders
            ]
            reference_map[gateway_name] = reference_types
        else:
            reference_map[gateway_name] = []
    return reference_map


def clean_null(v):
    if v in (None, "null", ""):
        return ""
    return v


def load_existing(context, id):
    frappe.flags.ignore_permissions = True
    doc = frappe.get_doc("Mpesa Express Request", id)
    if not doc:
        context.error = _("Request not found")
        context.is_new = True
        context.mpesa_request = {}
        return

    else:
        context.mpesa_request = {
            "phone_number": doc.phone_number,
            "payment_gateway": doc.payment_gateway,
            "reference_type": doc.reference_doctype,
            "reference_id": doc.reference_name,
            "amount": doc.amount,
            "checkout_request_id": doc.checkout_request_id,
            "status": doc.status,
            "response_description": doc.response_description,
        }
        if doc.status == "Completed":
            context.success = _("Payment completed successfully")
        elif doc.status == "Failed":
            context.error = _("Payment failed: ") + doc.response_description
