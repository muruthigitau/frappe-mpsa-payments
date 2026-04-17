import frappe
from frappe.model.document import Document


def on_submit(doc: Document, method: str = None) -> None:
    submit_b2c_disbursement(doc.name)


def submit_b2c_disbursement(name: str) -> None:
    doc = frappe.get_doc("Payment Request", name)
    if doc.payment_request_type == "Outward":
        if not doc.phone_number:
            frappe.throw("Phone Number is required for Outward Payment Requests")

        mpesa_settings = frappe.db.get_value(
            "Payment Gateway", doc.payment_gateway, "gateway_controller"
        )

        if not mpesa_settings:
            frappe.throw(
                f"Payment Gateway {doc.payment_gateway} does not have a gateway controller set"
            )

        b2c_disbursement = {
            "name": None,
            "payment_type": "Mpesa Disbursement",
        }

        ref_doc = frappe.get_doc(doc.reference_doctype, doc.reference_name)

        ref = {
            "doctype": doc.doctype,
            "name": doc.name,
            "allocated_amount": float(doc.grand_total),
            "reference_name": doc.name,
            "reference_doctype": doc.doctype,
            "party_type": "Customer",
            "party": ref_doc.customer if ref_doc.customer else None,
            "partyb": doc.phone_number,
        }

        create_b2c_request(ref, mpesa_settings, b2c_disbursement)


def create_b2c_request(ref, settings_name, b2c_disbursement):
    try:
        payment_type = b2c_disbursement.get("payment_type")

        data = {
            "doctype": "B2C Disbursement Request",
            "amount": ref.get("allocated_amount"),
            "reference_doctype": ref.get("reference_doctype"),
            "reference_name": ref.get("reference_name"),
            "party_type": ref.get("party_type"),
            "party": ref.get("party"),
        }

        if payment_type in ("Mpesa Disbursement", "Stanbic Mobile"):
            data["phone_number"] = ref.get("partyb")
        elif payment_type == "Stanbic PesaLink":
            data["bank_ac_no"] = ref.get("partyb")
            data["bank_name"] = ref.get("bank_name")
            data["bank_code"] = ref.get("bank_code")

        if payment_type == "Mpesa Disbursement":
            data["payment_provider"] = "Mpesa"
            data["mpesa_settings"] = settings_name
        elif payment_type in ("Stanbic Mobile", "Stanbic PesaLink"):
            data["payment_provider"] = "Stanbic"
            data["stanbic_settings"] = settings_name

        b2c_request = frappe.get_doc(data)
        b2c_request.insert(ignore_permissions=True)
        b2c_request.submit()

    except Exception as e:
        frappe.log_error(
            title="Failed to create B2C Request", message=frappe.get_traceback()
        )
        frappe.throw(f"Failed to create B2C Request {e}")
