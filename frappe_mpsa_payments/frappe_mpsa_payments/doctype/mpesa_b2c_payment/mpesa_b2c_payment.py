# Copyright (c) 2024, Navari Limited and contributors
# For license information, please see license.txt

# import frappe

import frappe
from frappe.model.document import Document

from ...api.mpsa_b2c import MpesaB2CConnector
from ....utils.definitions import B2CRequestDefinition
from .. import app_logger
from ..custom_exceptions import InformationMismatchError

import uuid

class MPesaB2CPayment(Document):
    """MPesa B2C Payment Class"""

    def _generate_uuid_v4(self):
        return str(uuid.uuid4())

    def _get_mpesa_settings(self) -> Document:
        """ Fetch and validate Mpesa Settings for the Payment Gateway."""

        try:
            setting: Document = frappe.get_doc(
                "Mpesa Settings",
                {"payment_gateway_name": self.mpesa_setting, "api_type": "MPesa B2C (Business to Customer)"},
                [
                    "name",
                    "initiator_name",
                    "security_credential",
                    "business_shortcode",
                    "consumer_key",
                    "consumer_secret",
                ],
                as_dict=True,
            )
        except frappe.DoesNotExistError:
            error_msg = f"Mpesa Settings not found for payment gateway: {self.mpesa_setting}"
            self.error = error_msg
            app_logger.error(error_msg)
            frappe.throw(error_msg, frappe.DoesNotExistError)

        return setting

    def _prepare_request_data(self, item, setting):
        """Prepares the B2C request payload"""
        return B2CRequestDefinition(
                    ConsumerKey=setting.consumer_key,
                    ConsumerSecret=setting.get_password("consumer_secret"),
                    OriginatorConversationID=item.originator_conversation_id,
                    InitiatorName=setting.initiator_name,
                    SecurityCredential=setting.security_credential,
                    CommandID=self.commandid,
                    Amount=item.amount,
                    PartyA=setting.business_shortcode,  # TODO: Consider this
                    PartyB=item.partyb,
                    Remarks=self.remarks,
                    Occassion=self.occassion,
                )

    def _process_payment_item(self, item, connector, setting, is_retry=False):
        """Handles a single B2C payment item"""
        try:
            if is_retry:
                item.error_code = ""
                item.error_description = ""
                item.payment_status = "Not Initiated"

            request_data = self._prepare_request_data(item, setting)

            response = connector.make_b2c_payment_request(
                request_data=request_data,
                doctype=item.doctype,
                document_name=item.name
            )

            if response.get("ResponseCode") == 0:
                item.payment_status = "Initiated"
            else:
                item.payment_status = "Failed"
                item.error_code = response.get("errorCode")
                item.error_description = response.get("errorMessage", "Unknown error")
                return False

        except Exception as e:
            item.payment_status = "Failed"
            item.error_description = str(e)
            error_msg = f"{'Retry' if is_retry else 'Initial'} error for item {item.name}: {str(e)}"
            app_logger.error(error_msg, exc_info=True)
            frappe.log_error(error_msg, "MPesa B2C Error")
            return False

        return True


    def validate(self) -> None:
        """Validations"""
        self.error = ""

        if self.party_type == "Employee":
            if self.commandid != "SalaryPayment":
                self.error = "Party Type 'Employee' requires Command ID 'SalaryPayment'"
                app_logger.error(self.error)
                raise InformationMismatchError(self.error)

        if self.party_type == "Supplier":
            if self.commandid != "BusinessPayment":
                self.error = (
                    "Party Type 'Supplier' requires Command ID 'BusinessPayment'"
                )
                app_logger.error(self.error)
                raise InformationMismatchError(self.error)

        if self.items:
            # Perform validations for child table records
            for item in self.items:
                item.validate()

    def before_save(self) -> None:
        """Initital payment trigger"""
        setting = self._get_mpesa_settings()

        connector = MpesaB2CConnector(settings_name=setting.name)
        any_errors = False

        for item in self.items:
            success = self._process_payment_item(item, connector, setting)
            if not success:
                any_errors = True

        if any_errors:
            frappe.msgprint(
                msg="Some B2C Payment Requests failed. Check item details.",
                title="Payment Request Error",
                indicator="red"
            )
        else:
            frappe.msgprint(
                "Payment Request Initiated.", title="Payment Request", indicator="green"
            )

    @frappe.whitelist()
    def retry_failed_payments(self) -> None:
        """Retry only failed payments"""
        setting = self._get_mpesa_settings()

        connector = MpesaB2CConnector(settings_name=setting.name)
        any_errors = False

        for item in self.items:
            if item.payment_status != "Failed":
                continue

            item.originator_conversation_id = self._generate_uuid_v4()

            item.save()

            success = self._process_payment_item(item, connector, setting, is_retry=True)
            if not success:
                any_errors = True

        if any_errors:
            frappe.msgprint("Some retries failed. Please review the payment items.", indicator="orange")
        else:
            frappe.msgprint("All failed payments retried successfully.", indicator="green")
        