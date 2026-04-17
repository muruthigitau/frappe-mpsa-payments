# Copyright (c) 2024, Navari Limited and contributors
# For license information, please see license.txt

import uuid

import frappe
from frappe.model.document import Document

from frappe_mpsa_payments.utils.utils import validate_phone_number

from ...api.b2c import make_b2c_payment_request


class B2CDisbursementRequest(Document):
    """B2C Payments Transactions"""

    def before_insert(self) -> None:
        """Insert Missing Values"""
        self.originator_conversation_id = self._generate_uuid_v4()

    def validate(self) -> None:
        """B2C Payments Transactions validations"""
        validate_phone_number(self.phone_number)
        self.phone_number = sanitize_mobile_number(self.phone_number)
        if not self.originator_conversation_id:
            self.originator_conversation_id = self._generate_uuid_v4()

        if self.stanbic_settings and not self.dbs_reference_id:
            self.dbs_reference_id = self._generate_uuid_v4()

    def on_submit(self):
        make_b2c_payment_request(self.name)

    def _generate_uuid_v4(self) -> str:
        return str(uuid.uuid4())

    @frappe.whitelist()
    def retry_failed_payment(self) -> None:
        """Retry only failed payments"""
        make_b2c_payment_request(self.name)


def sanitize_mobile_number(number: str) -> str:
    """Strip all non-digit characters, take the last 9 digits, and add country code."""
    sanitized_number = "".join(filter(str.isdigit, number))[-9:]
    return "254" + sanitized_number
