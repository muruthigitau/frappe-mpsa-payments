import frappe
from frappe import _
from frappe_mpsa_payments.utils.utils import convert_amount_to_kes


def get_context(context):
    q = frappe.local.form_dict
    context.redirect_to = q.get("redirect_to")
    context.mpesa_gateways = frappe.get_all(
        "Payment Gateway",
        filters={"gateway_settings": ["is", "set"]},
        fields=["name"],
        ignore_permissions=True,
    )

    currency = q.get("currency") or "KES"
    context.currency = currency
    gateway = q.get("payment_gateway")
    setting_name = gateway.replace("Mpesa-", "") if gateway else None
    settings = frappe.get_doc("Mpesa Settings", setting_name) if setting_name else None

    context.title = settings.payment_page_title if settings and settings.payment_page_title else q.get("title")
    setting_desc = settings.payment_page_description if settings else None
    query_desc = q.get("description")
    context.description = f"{setting_desc} - {query_desc}" if setting_desc and query_desc else (setting_desc or query_desc)

    context.allow_amount_editing = settings.allow_amount_editing if settings else False
    context.allow_payment_reference_editing = settings.allow_payment_reference_editing if settings else False
    

    if q.get("id"):
        context.is_new = False
        load_existing(context, q.get("id"))
        frappe.local.form_dict = {"id": q.get("id"), "redirect_to": context.redirect_to}
    else:
        context.is_new = True
        base_amount = clean_null(q.get("base_amount") or q.get("amount"))
        actual_amount = base_amount

        if currency != "KES" and base_amount:
            try:
                actual_amount = convert_amount_to_kes(
                    amount=float(base_amount), currency=currency, settings= setting_name
                )
            except Exception as e:
                actual_amount = base_amount

        context.mpesa_request = {
            "phone_number": clean_null(q.get("phone_number")),
            "payment_gateway": gateway,
            "reference_type": clean_null(q.get("reference_type")),
            "reference_id": clean_null(q.get("reference_id")),
            "base_amount": base_amount,
            "currency": currency,
            "amount": actual_amount,
            "title": context.title,
            "description": context.description,
        }


def clean_null(v):
    if v in (None, "null", "", "undefined"):
        return ""
    return v


def load_existing(context, id):
    try:
        doc = frappe.get_doc("Mpesa Express Request", id)
        context.mpesa_request = {
            "phone_number": doc.phone_number,
            "payment_gateway": doc.payment_gateway,
            "reference_type": doc.reference_doctype,
            "reference_id": doc.reference_name,
            "base_amount": getattr(doc, "base_amount", doc.amount),
            "amount": doc.amount,
            "currency": getattr(doc, "currency", "KES"),
            "checkout_request_id": doc.checkout_request_id,
            "status": doc.status,
            "response_description": doc.response_description,
            "title": doc.transaction_title,
            "description": doc.transaction_description,
        }
        
        if doc.status == "Completed":
            context.success = _("Payment completed successfully")
        elif doc.status == "Failed":
            context.error = _("Payment failed: ") + (
                doc.response_description or "Unknown Error"
            )
    except frappe.DoesNotExistError:
        context.error = _("Request not found")
        context.is_new = True
        context.mpesa_request = {}
