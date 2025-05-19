# Copyright (c) 2024, Navari Limited and contributors
# For license information, please see license.txt

from typing import Dict, List, Optional
import uuid


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate
from erpnext.accounts.utils import get_account_currency
from erpnext.setup.utils import get_exchange_rate

from ...api.mpsa_b2c import MpesaB2CConnector
from ....utils.definitions import B2CRequestDefinition
from .. import app_logger
from ..custom_exceptions import InformationMismatchError


class B2CPaymentDisbursement(Document):
    """MPesa B2C Payment Class"""

    def validate(self) -> None:
        """Validations for the document and references."""
        self.error = ""
        self.validate_mandatory_fields()
        self.validate_mode_of_payment()
        self.validate_party_type()
        for ref in self.references:
            ref.validate()
        self.validate_amounts()

    def before_save(self) -> None:
        """Set missing values before saving."""
        self.set_missing_values()

    def before_submit(self) -> None:
        """Initital payment trigger"""
        if self.payment_type == "Mpesa Disbursement":
            setting = self._get_mpesa_settings()
            connector = MpesaB2CConnector(settings_name=setting.name)

            any_errors = self._process_mpesa_b2c_payments(connector, setting)

            frappe.msgprint(
                msg="Some B2C Payment Requests failed. Please Retry." if any_errors else "Payment Request Initiated.",
                title="Payment Request Error" if any_errors else "Payment Request",
                indicator="red" if any_errors else "green"
            )

        self.on_update()
        self.db_set("status", self.status)

    def on_update(self) -> None:
        """Update overall status based on payment references"""
        print("Why am I not being called?")
        if not self.references:
            self.status = "Not Initiated"
            return
        
        statuses = [ref.payment_status for ref in self.references]

        print(statuses)

        if all(status == "Paid" for status in statuses):
            self.status = "Paid"
        elif all(status == "Failed" for status in statuses):
            self.status = "Failed"
        elif all(status == "Not Initiated" for status in statuses):
            self.status = "Not Initiated"
        elif any(status == "Paid" for status in statuses):
            self.status = "Partially Paid"
        else:
            self.status = "Not Initiated"

    def validate_mandatory_fields(self) -> None:
        mandatory_fields = ["company", "posting_date", "party_type", "paid_from", "paid_to", "paid_amount"]
        for field in mandatory_fields:
            if not self.get(field):
                frappe.throw(f"Field {self.meta.get_label(field)} is mandatory.")

            if not self.references:
                frappe.throw("At least one reference is required")

    def validate_mode_of_payment(self) -> None:
        if not self.mode_of_payment:
            frappe.throw(f"Mode of Payment is required")

        if self.payment_type == "Mpesa Disbursement":
            mpesa_setting = frappe.db.get_value("Mpesa Settings", self.mode_of_payment[6:], "name")
            self.mpesa_setting = mpesa_setting

    def validate_party_type(self) -> None:
        if self.party_type not in ["Employee", "Supplier"]:
            frappe.throw("Party Type must be Employee or Supplier")

    def validate_amounts(self) -> None:
        """Validate paid_amount and base_paid_amount."""
        if flt(self.paid_amount) <= 0:
            frappe.throw("Paid Amount must be greater than zero")
        if not self.base_paid_amount and self.paid_from_account_currency != "KES":
            frappe.throw("Base Paid Amount (KES) is required for M-Pesa")
        
        total_allocated = sum(flt(row.allocated_amount) for row in self.references)
        if flt(total_allocated) != flt(self.paid_amount):
            frappe.throw(f"Total allocated amount {total_allocated} must equal Paid Amount {self.paid_amount}")

    def set_missing_values(self):
        if not self.company_currency:
            self.company_currency = frappe.get_cached_value("Company", self.company, "default_currency")

        if not self.source_exchange_rate:
            self.source_exchange_rate = get_exchange_rate(
                self.paid_from_account_currency, self.company_currency, self.posting_date
            )

        if self.paid_from_account_currency != "KES" and self.paid_amount:
            kes_rate = get_exchange_rate(self.company_currency, "KES", self.posting_date)
            self.base_paid_amount = flt(self.paid_amount * self.source_exchange_rate) / flt(kes_rate)
        
    def _generate_uuid_v4(self) -> str:
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

    def _prepare_request_data(self, ref, setting) -> None:
        """Prepares the B2C request payload"""
        return B2CRequestDefinition(
            ConsumerKey=setting.consumer_key,
            ConsumerSecret=setting.get_password("consumer_secret"),
            OriginatorConversationID=ref.originator_conversation_id,
            InitiatorName=setting.initiator_name,
            SecurityCredential=setting.security_credential,
            CommandID=self.commandid,
            Amount=ref.allocated_amount,
            PartyA=setting.business_shortcode,  # TODO: Consider this
            PartyB=ref.partyb,
            Remarks=self.remarks,
            Occassion=self.occassion,
        )

    def _process_payment_ref(self, ref, connector, setting, is_retry=False) -> bool:
        """Handles a single B2C payment reference"""
        try:

            request_data = self._prepare_request_data(ref, setting)

            response = connector.make_b2c_payment_request(
                request_data=request_data,
                doctype=ref.reference_doctype,
                document_name=ref.reference_name
            )

            if response.get("ResponseCode") == "0":
                ref.payment_status = "Initiated"
            else:
                ref.payment_status = "Failed"
                return False

        except Exception as e:
            ref.payment_status = "Failed"
            error_msg = f"{'Retry' if is_retry else 'Initial'} error for ref {ref.reference_name}: {str(e)}"
            app_logger.error(error_msg, exc_info=True)
            frappe.log_error(error_msg, "MPesa B2C Error")
            return False

        return True
    
    def _process_mpesa_b2c_payments(self, connector, setting, only_failed=False, is_retry=False) -> bool:
        any_errors = False

        for ref in self.references:
            if only_failed and ref.payment_status != "Failed":
                continue

            if is_retry:
                ref.originator_conversation_id = self._generate_uuid_v4()
                ref.save()

            success = self._process_payment_ref(ref, connector, setting, is_retry=is_retry)
            if not success:
                any_errors = True

        return any_errors

    @frappe.whitelist()
    def retry_failed_payments(self) -> None:
        """Retry only failed payments"""
        if self.payment_type == "Mpesa Disbursement":
            setting = self._get_mpesa_settings()
            connector = MpesaB2CConnector(settings_name=setting.name)

            any_errors = self._process_mpesa_b2c_payments(connector, setting, only_failed=True, is_retry=True)

            frappe.msgprint(
                msg="Some B2C Payment retries failed. Please Retry." if any_errors else "Payment Request Initiated.",
                title="Payment Request Error" if any_errors else "Payment Request",
                indicator="red" if any_errors else "green"
            )

        self.on_update()
        self.db_set("status", self.status)

    @frappe.whitelist()
    def get_outstanding_reference_documents(self, args: Dict) -> List[Dict]:
        """
        Fetch outstanding references based on filters.
        
        Args:
            args: Dictionary containing filter parameters
            
        Returns:
            List of outstanding reference documents
        """
        args = args.get("args", args) if isinstance(args, dict) else args


        # Configuration for different document types
        DOCTYPE_CONFIG = {
            "Employee Advance": {
                "fields": ["name", "posting_date", "employee", "currency", "advance_amount", 
                        "paid_amount", "pending_amount", "claimed_amount"],
                "date_field": "posting_date",
                "additional_filters": {}
            },
            "Expense Claim": {
                "fields": ["name", "posting_date", "employee", "grand_total", 
                        "total_claimed_amount", "total_amount_reimbursed"],
                "date_field": "posting_date",
                "additional_filters": {"approval_status": "Approved", "status": "Unpaid"}
            },
            "Purchase Invoice": {
                "fields": ["name", "posting_date", "supplier", "grand_total", 
                        "outstanding_amount", "due_date", "currency", "base_rounded_total", "rounded_total"],
                "date_field": "posting_date",
                "additional_filters": {"outstanding_amount": [">", 0]}
            },
            "Purchase Order": {
                "fields": ["name", "transaction_date", "supplier", "grand_total", 
                        "advance_paid", "schedule_date", "currency", "base_rounded_total", "rounded_total"],
                "date_field": "transaction_date",
                "additional_filters": {}
            },
            "Salary Slip": {
                "fields": ["name", "posting_date", "employee", "net_pay", "currency", "journal_entry"],
                "date_field": "posting_date",
                "additional_filters": {}
            }
        }

        doctype = args["transaction_to_pay_against"]
        config = DOCTYPE_CONFIG.get(doctype)
        if not config:
            frappe.throw(_("Invalid transaction type"))

        filters = self._build_filters(args, config)

        entries = self._fetch_entries(doctype, config["fields"], filters, config["date_field"])
        
        return self._process_entries(entries, args, doctype, config["date_field"])

    def _build_filters(self, args: Dict, config: Dict) -> Dict:
        """Build database query filters."""
        filters = {
            "docstatus": 1,
            "company": args["company"],
            **config["additional_filters"]
        }

        date_field = config["date_field"]
        
        if from_date := args.get("from_posting_date"):
            filters[date_field] = [">=", from_date]
        if to_date := args.get("to_posting_date"):
            filters[date_field] = ["<=", to_date]
        if from_date and to_date:
            filters[date_field] = ["between", [from_date, to_date]]

        due_date_field = "due_date" if args["transaction_to_pay_against"] == "Purchase Invoice" else "schedule_date"
        if from_due_date := args.get("from_due_date"):
            filters[due_date_field] = [">=", from_due_date]
        if to_due_date := args.get("to_due_date"):
            filters[due_date_field] = ["<=", to_due_date]
        if from_due_date and to_due_date:
            filters[due_date_field] = ["between", [from_date, to_date]]

        if greater_than := args.get("outstanding_amt_greater_than"):
            filters["outstanding_amount"] = [">", greater_than]
        if less_than := args.get("outstanding_amt_less_than"):
            if greater_than:
                filters["outstanding_amount"] = ["between", [greater_than, less_than]]
            else:
                filters["outstanding_amount"] = ["<", less_than]

        return filters

    def _fetch_entries(self, doctype: str, fields: List[str], filters: Dict, date_field: str) -> List[Dict]:
        """Fetch documents from database."""
        try:
            entries = frappe.db.get_all(
                doctype,
                filters=filters,
                fields=fields,
                order_by=f"{date_field} asc",
                limit=1000
            )
        except Exception as e:
            frappe.log_error(f"Error fetching {doctype}: {str(e)}")
            frappe.msgprint(
                _(f"Failed to fetch {doctype} references"),
                title=_("Error"),
                indicator="red"
            )
            return []
        
        if doctype == "Employee Advance":
            entries = [e for e in entries if (e.paid_amount or 0) < (e.advance_amount or 0)]
        
        return entries

    def _process_entries(self, entries: List[Dict], args: Dict, doctype: str, date_field: str) -> List[Dict]:
        """Process entries into reference format."""
        if not entries:
            frappe.msgprint(
                _("No outstanding references found for the specified filters"),
                title=_("No Outstanding References"),
                indicator="green"
            )
            return []

        references = []
        for entry in entries:
            payable_amount = self._compute_payable_amount(entry, doctype)
            if payable_amount <= 0:
                continue

            party = entry.get("employee") or entry.get("supplier")
            if not party:
                continue

            references.append({
                "voucher_type": doctype,
                "voucher_no": entry.name,
                "party": party,
                "due_date": entry.get("due_date") or entry.get("schedule_date"),
                "invoice_amount": self._get_invoice_amount(entry, doctype),
                "outstanding_amount": payable_amount,
                "allocated_amount": 0,
                "currency": entry.currency or self.company_currency,
                "exchange_rate": self._get_exchange_rate(entry, doctype),
                "partyb": self.get_party_phone(entry, args["party_type"])
            })

        return references

    def _compute_payable_amount(self, entry: Dict, doctype: str) -> float:
        """Calculate payable amount for a document."""
        PAYABLE_AMOUNT_CALC = {
            "Employee Advance": lambda e: (e.advance_amount or 0) - (e.paid_amount or 0),
            "Expense Claim": lambda e: (e.total_claimed_amount or 0) - (e.total_amount_reimbursed or 0)
        }
        
        return PAYABLE_AMOUNT_CALC.get(doctype, lambda e: (
            e.get("base_rounded_total") or e.get("rounded_total") or 0
        ))(entry)

    def _get_invoice_amount(self, entry: Dict, doctype: str) -> float:
        """Calculate invoice amount based on document type."""
        INVOICE_AMOUNT_FIELD = {
            "Expense Claim": "total_claimed_amount",
            "Salary Slip": "net_pay",
            "Employee Advance": "advance_amount"
        }
        
        field = INVOICE_AMOUNT_FIELD.get(doctype, "grand_total")
        return entry.get(field, 0)

    def _get_exchange_rate(self, entry: Dict, doctype: str) -> float:
        """Calculate exchange rate for the document."""
        if self.paid_to_account_currency == self.company_currency:
            return 1
        
        return get_exchange_rate(
            entry.get("currency") or self.company_currency,
            self.company_currency,
            entry.get("posting_date")
        )

    def get_party_phone(self, entry: Dict, party_type: str) -> str:
        """Get phone number for party."""
        if party_type == "Employee":
            return frappe.db.get_value("Employee", entry.employee, "cell_number") or ""
        
        if party_type == "Supplier":
            contact = frappe.db.get_all(
                "Contact", 
                filters={"link_name": entry.supplier}, 
                fields=["phone", "mobile_no"],
                limit=1
            )
            return contact[0].get("phone") or contact[0].get("mobile_no") or "" if contact else ""
        
        return ""
