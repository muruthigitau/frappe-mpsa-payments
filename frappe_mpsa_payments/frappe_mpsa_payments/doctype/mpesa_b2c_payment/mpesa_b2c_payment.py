# Copyright (c) 2024, Navari Limited and contributors
# For license information, please see license.txt

# import frappe

import frappe
from frappe.model.document import Document

from ...api.mpsa_b2c import MpesaB2CConnector
from ....utils.definitions import B2CRequestDefinition
from .. import app_logger
from ..custom_exceptions import InformationMismatchError

class MPesaB2CPayment(Document):
    """MPesa B2C Payment Class"""

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

        if not setting:
            error_msg = f"Mpesa Settings not found for payment gateway: {self.mpesa_setting}"
            self.error = error_msg
            app_logger.error(error_msg)
            frappe.throw(error_msg, frappe.DoesNotExistError)

        connector = MpesaB2CConnector(settings_name=setting.name)
        any_errors = False

        for item in self.items:
            try:
                request_data = B2CRequestDefinition(
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
            
                response = connector.make_b2c_payment_request(
                    request_data=request_data,
                    doctype=item.doctype,
                    document_name=item.name
                )

                if response.get("ResponseCode") == "0":
                    item.payment_status = "Initiated"
                else:
                    item.payment_status = "Failed"
                    error_msg = response.get("ResultDesc", "Unknown error")
                    item.error_description = error_msg
                    any_errors = True

            except Exception as e:
                any_errors = True
                item.payment_status = "Failed"
                item.error_description = str(e)
                error_msg = f"Error processing B2C payment {str(e)}"
                self.error_description = f"{self.error}\n{error_msg}" if self.error else error_msg
                app_logger.error(error_msg, exc_info=True)
                frappe.log_error(error_msg, "MPesa B2C Payment Error")

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
