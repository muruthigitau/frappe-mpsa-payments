# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from ...api.m_pesa_api import initiate_b2c_disbursement  


class MpesaB2CDisbursementRequest(Document):
    def validate(self):
        if self.settings:
            self.payment_gateway = frappe.db.get_value(
                "Payment Gateway", {"gateway_controller": self.settings}, "name"
            )

    def on_submit(self):
        self.make_disbursement()
        
    def make_disbursement(self):
        args = {
            "document_name": self.name,
            "payment_gateway": self.payment_gateway,
            "phone_number": self.phone_number,
            "request_amount": self.amount,
            "doctype": self.doctype, 
            "document_name": self.name,
            "reference_name": self.reference_name,
            "command_id": self.command_id,
        }

        try:
            initiate_b2c_disbursement(**args)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "STK Push Error")
            frappe.throw(f"Failed to initiate STK push: {str(e)}")
