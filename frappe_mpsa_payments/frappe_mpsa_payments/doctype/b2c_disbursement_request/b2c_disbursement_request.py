# Copyright (c) 2024, Navari Limited and contributors
# For license information, please see license.txt

import uuid

import frappe
from frappe.model.document import Document

from ....utils.definitions import B2CRequestDefinition
from ...api.b2c import make_b2c_payment_request
from .. import app_logger


class B2CDisbursementRequest(Document):
    """B2C Payments Transactions"""

    def before_insert(self) -> None:
        """Insert Missing Values"""
        self.originator_conversation_id = self._generate_uuid_v4()

    def validate(self) -> None:
        """B2C Payments Transactions validations"""
        if not self.originator_conversation_id:
            self.originator_conversation_id = self._generate_uuid_v4()

    def on_submit(self):
        make_b2c_payment_request(self.name)

    def _generate_uuid_v4(self) -> str:
        return str(uuid.uuid4())

    def _prepare_request_data(self, setting) -> None:
        """Prepares the B2C request payload"""
        setting = frappe.get_doc("Mpesa Settings", self.mpesa_settings)

        return B2CRequestDefinition(
            ConsumerKey=setting.consumer_key,
            ConsumerSecret=setting.get_password("consumer_secret"),
            OriginatorConversationID=self.originator_conversation_id,
            InitiatorName=setting.initiator_name,
            SecurityCredential=setting.security_credential,
            CommandID=self.commandid,
            Amount=self.amount,
            PartyA=setting.business_shortcode,  # TODO: Consider this
            PartyB=self.phone_number,
            Remarks=self.remarks,
            Occassion=self.occassion,
        )

    def _process_payment_ref(self, is_retry=False) -> bool:
        """Handles a single B2C payment reference"""
        try:
            request_data = self._prepare_request_data(self.mpesa_settings)

            response = make_b2c_payment_request(
                request_data=request_data,
                doctype=self.doctype,
                document_name=self.name,
                mpesa_settings=self.mpesa_settings,
            )

            if response.get("ResultCode") == "0":
                self.status = "Initiated"
            else:
                self.status = "Failed"
                return False

        except Exception as e:
            self.status = "Failed"
            error_msg = f"{'Retry' if is_retry else 'Initial'} error for ref {self.reference_name}: {str(e)}"
            app_logger.error(error_msg, exc_info=True)
            frappe.log_error(error_msg, "MPesa B2C Error")
            return False

        return True

    def _process_b2c_disbursement_request(
        self, only_failed=False, is_retry=False
    ) -> bool:
        any_errors = False

        if only_failed and self.status != "Failed":
            return False

        if is_retry:
            self.originator_conversation_id = self._generate_uuid_v4()
            self.save()

        success = self._process_payment_ref(is_retry=is_retry)
        if not success:
            any_errors = True

        return any_errors

    @frappe.whitelist()
    def retry_failed_payment(self) -> None:
        """Retry only failed payments"""

        any_errors = self._process_b2c_disbursement_request(
            only_failed=True, is_retry=True
        )

        frappe.msgprint(
            msg="B2C Payment request retry failed. Please Retry."
            if any_errors
            else "B2C Payment Request Initiated.",
            title="Payment Request Error" if any_errors else "Payment Request",
            indicator="red" if any_errors else "green",
        )
