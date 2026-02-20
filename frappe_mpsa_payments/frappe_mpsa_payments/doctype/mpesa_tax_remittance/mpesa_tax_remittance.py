# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from ...api.m_pesa_api import (
    initiate_tax_remmitance,
)


class MpesaTaxRemittance(Document):
    def validate(self):
        self.set_missing_values()

    def set_missing_values(self):
        if not self.mpesa_settings and self.mode_of_payment:
            if self.mode_of_payment.startswith("Mpesa-"):
                self.mpesa_settings = self.mode_of_payment.split("Mpesa-", 1)[1]

        if self.mpesa_settings and not self.payment_gateway:
            self.payment_gateway = frappe.db.get_value(
                "Payment Gateway", {"gateway_controller": self.mpesa_settings}, "name"
            )

        if self.payment_gateway and not self.mpesa_settings:
            self.mpesa_settings = frappe.db.get_value(
                "Payment Gateway", {"name": self.payment_gateway}, "gateway_controller"
            )

    def on_submit(self):
        self.initiate_request()

    @frappe.whitelist()
    def initiate_request(self):
        args = {
            "request_amount": self.amount,
            "doctype": self.doctype,
            "document_name": self.name,
            "account_reference": self.account_reference,
            "mpesa_settings": self.mpesa_settings,
        }

        try:
            initiate_tax_remmitance(**args)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "Tax Remittance on Submit Error")
            frappe.throw(f"Failed to initiate Tax Remittance: {str(e)}")
