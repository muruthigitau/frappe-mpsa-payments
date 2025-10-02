# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document

from ....utils.utils import validate_phone_number
from ...api.m_pesa_api import initiate_stk_push  # Import the STK push function


class MpesaExpressRequest(Document):
    def validate(self):
        if self.settings:
            self.payment_gateway = frappe.db.get_value(
                "Payment Gateway", {"gateway_controller": self.settings}, "name"
            )

        if self.reference_doctype == "Payment Request":
            self.validate_payment_request_amount()

        if not validate_phone_number(self.phone_number):
            frappe.throw(
                "Invalid phone number format. Please ensure it is in the correct format, e.g., 254712345678."
            )

        self.validate_duplicate_c2b_records()

    def validate_duplicate_c2b_records(self):
        """Ensure any duplicate C2B is neutralized in favour of this Express Request."""
        if not self.transaction_id:
            return

        c2b_name = frappe.db.exists(
            "Mpesa C2B Payment Register", {"transid": self.transaction_id}
        )

        if not c2b_name:
            return

        frappe.db.savepoint("before_c2b_neutralize")
        try:
            c2b_doc = frappe.get_doc("Mpesa C2B Payment Register", c2b_name)

            if c2b_doc.docstatus == 1:
                c2b_doc.cancel()
            else:
                c2b_doc.delete()

            frappe.log_error(
                message=f"Neutralised duplicate C2B {c2b_doc.name} in favour of Express Request {self.name}",
                title="Mpesa Express vs C2B Duplicate",
            )

        except Exception:
            frappe.db.rollback(save_point="before_c2b_neutralize")
            frappe.log_error(
                frappe.get_traceback(),
                f"Error neutralising duplicate C2B {c2b_name} for Express Request {self.name}",
            )

    def validate_payment_request_amount(self):
        payment_request = frappe.get_doc("Payment Request", self.reference_name)
        currency = payment_request.currency
        company = payment_request.company
        company_currency = frappe.db.get_value("Company", company, "default_currency")

        if currency != "KES":
            if payment_request.reference_doctype and payment_request.reference_name:
                ref_doc = frappe.get_doc(
                    payment_request.reference_doctype, payment_request.reference_name
                )
                conversion_rate = getattr(ref_doc, "conversion_rate", None)

                if company_currency != "KES":
                    frappe.throw(
                        "STK Push can only be initiated if document or company currency is KES. "
                        f"Current currency: {currency}, Company currency: {company_currency}"
                    )

                if not conversion_rate:
                    frappe.throw(
                        "Conversion rate not available to convert amount to KES."
                    )

                self.amount = float(payment_request.grand_total) * float(
                    conversion_rate
                )
            else:
                frappe.throw("Missing reference document to determine conversion rate.")

    def on_submit(self):
        args = {
            "payment_gateway": self.payment_gateway,
            "phone_number": self.phone_number,
            "request_amount": self.amount,
            "doctype": self.doctype,
            "document_name": self.name,
            "reference_name": self.reference_name,
        }

        try:
            initiate_stk_push(**args)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "STK Push on Submit Error")
            frappe.throw(f"Failed to initiate STK Push: {str(e)}")
