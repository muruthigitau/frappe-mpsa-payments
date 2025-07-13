# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document

from ....utils.utils import (
    create_payment_gateway,
    create_payment_gateway_account,
    validate_phone_number,
)
from .stanbic_connector import StanbicConnector


class StanbicSettings(Document):
    def validate(self):
        if not self.mobile_number:
            return

        digits = re.sub(r"\D", "", self.mobile_number)

        if not validate_phone_number(digits):
            frappe.throw(
                _("Invalid phone number: {0}").format(self.mobile_number),
                title=_("Validation Error"),
            )

        if digits.startswith("0"):
            digits = "254" + digits[1:]

        self.mobile_number = digits

    def after_insert(self):
        self._ensure_gateway_and_modes()

    def on_update(self):
        self._ensure_gateway_and_modes()

    def _ensure_gateway_and_modes(self):
        gateway_name = f"Stanbic-{self.payment_gateway_name}"
        create_payment_gateway(
            gateway=gateway_name, settings="Stanbic Settings", controller=self.name
        )

        create_payment_gateway_account(
            gateway=gateway_name,
            payment_channel="Email",
            company=self.company,
        )

        frappe.db.commit()

        self._ensure_mode_of_payment(
            mode_label=f"{gateway_name}-Mobile",
            gateway=gateway_name,
            payment_type="Phone",
        )

        self._ensure_mode_of_payment(
            mode_label=f"{gateway_name}-PesaLink",
            gateway=gateway_name,
            payment_type="Bank",
        )

    def _ensure_mode_of_payment(self, mode_label: str, gateway: str, payment_type: str):
        """Create a Mode of Payment doc if it doesn't already exist."""
        # find the default account for this gateway
        pg_account = frappe.db.get_value(
            "Payment Gateway Account", {"payment_gateway": gateway}, "payment_account"
        )
        if not pg_account:
            frappe.throw(f"No Payment Gateway Account found for {gateway}")

        if not frappe.db.exists("Mode of Payment", mode_label):
            mop = frappe.get_doc(
                {
                    "doctype": "Mode of Payment",
                    "mode_of_payment": mode_label,
                    "payment_gateway": gateway,
                    "enabled": 1,
                    "type": payment_type,
                    "accounts": [
                        {
                            "doctype": "Mode of Payment Account",
                            "company": self.company,
                            "default_account": pg_account,
                        }
                    ],
                }
            )
            mop.insert(ignore_permissions=True)
            mop.save()

    @frappe.whitelist()
    def refresh_access_token(self):
        """
        Manually trigger fetching a fresh OAuth2 token from Stanbic,
        update the Settings record, and report back the new expiry.
        """

        conn = StanbicConnector(self.name)
        try:
            new_token = conn._get_token(manual_refresh=True)
            expiry = conn._token_expiry
            frappe.msgprint(
                _("Token refreshed successfully."), title=_("Stanbic Token")
            )
            return {"token": new_token, "expiry": expiry}
        except Exception as e:
            frappe.msgprint(
                _(f"Failed to refresh token: {e}"),
                title=_("Stanbic Token Error"),
                indicator="red",
            )
            raise
