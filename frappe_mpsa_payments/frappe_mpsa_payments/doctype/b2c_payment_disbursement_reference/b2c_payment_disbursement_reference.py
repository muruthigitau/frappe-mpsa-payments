# Copyright (c) 2024, Navari Limited and contributors
# For license information, please see license.txt

# import frappe
import re
from uuid import uuid4

import frappe
from frappe.utils import flt
from frappe.model.document import Document


class B2CPaymentDisbursementReference(Document):
    def validate(self) -> None:
        """Validation Hook"""
        if not self.originator_conversation_id:
            self.originator_conversation_id = str(uuid4())

        if not self.party:
            frappe.throw(
                f"Row #{self.idx}: Party is mandatory",
                frappe.ValidationError,
                title="Validation Error"
            )

        if self.allocated_amount is not None and flt(self.allocated_amount) < 10:
            frappe.throw(
                "Allocated Amount cannot be less than Kshs. 10",
                frappe.ValidationError,
                title="Validation Error",
            )

        if self.outstanding_amount and (self.allocated_amount > self.outstanding_amount or not self.outstanding_amount):
            frappe.throw(
                "Allocated Amount cannot be greater than Outstanding Amount",
                frappe.ValidationError,
                title="Validation Error",
            )

        if self.partyb:
            mobile_no = sanitise_phone_number(self.partyb)

            if not is_valid_receiver_contact(mobile_no):
                frappe.throw(
                    f"Incorrect Receiver's Mobile Number: {self.partyb}",
                    frappe.ValidationError,
                    title="Incorrect Contact",
                )

            self.partyb = mobile_no


def sanitise_phone_number(phone_number: str) -> str:
    """Sanitises a given phone_number string"""
    phone_number = phone_number.replace("+", "").replace(" ", "")

    regex = re.compile(r"^0\d{9}$")
    if not regex.match(phone_number):
        return phone_number

    phone_number = "254" + phone_number[1:]
    return phone_number


def is_valid_receiver_contact(receiver: str) -> bool:
    """Validates the Receiver's mobile number"""
    receiver = receiver.replace("+", "").strip()
    pattern1 = re.compile(r"^2547\d{8}$")
    pattern2 = re.compile(r"(25410|25411)\d{7}$")

    if receiver.startswith("2547"):
        return bool(pattern1.match(receiver))

    return bool(pattern2.match(receiver))
