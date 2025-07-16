# Copyright (c) 2024, Navari Limited and contributors
# For license information, please see license.txt

import uuid

import frappe
from frappe.model.document import Document

from ...api.b2c import make_b2c_payment_request


class B2CDisbursementRequest(Document):
    """B2C Payments Transactions"""

    def before_insert(self) -> None:
        """Insert Missing Values"""
        self.originator_conversation_id = self._generate_uuid_v4()

    def validate(self) -> None:
        """B2C Payments Transactions validations"""
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
        # TODO: we-write this part to accommodate the new classes.
        pass
