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
from erpnext.accounts.party import get_party_account
from erpnext.accounts.doctype.payment_entry.payment_entry import get_outstanding_reference_documents as original_get_outstanding_reference_documents

from ...api.mpsa_b2c import MpesaB2CConnector
from ....utils.definitions import B2CRequestDefinition
from .. import app_logger
from ..custom_exceptions import InformationMismatchError
from .config import DOCTYPE_CONFIGS, DoctypeConfig


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
        self.validate_reference_doctypes()

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
        if not self.references:
            self.status = "Not Initiated"
            return
        
        statuses = [ref.payment_status for ref in self.references]

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
        mandatory_fields = ["company", "posting_date", "party_type", "paid_from", "paid_to"]
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

    def validate_reference_doctypes(self) -> None:
        for ref in self.references:
            if ref.reference_doctype != self.transaction_to_pay_against:
                frappe.throw(
                    f"Reference doctype '{ref.reference_doctype}' does not match '{self.transaction_to_pay_against}' for row {ref.idx}."
                )

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
        doctype = args["transaction_to_pay_against"]
        config = self._get_doctype_config(doctype)
        filters = self._build_filters(args, config)
        entries = self._fetch_entries(doctype, config, args, filters)
        return self._populate_references(entries, args, doctype, config.date_field)
        

    def _get_doctype_config(self, doctype: str) -> DoctypeConfig:
        """
        Retrieve configuration for the specified doctype.

        Args:
            doctype: Document type name.

        Returns:
            DoctypeConfig object for the given doctype.
        """
        if not (config := DOCTYPE_CONFIGS.get(doctype)):
            frappe.throw("Invalid transaction type")
        return config

    def _build_filters(self, args: Dict, config: DoctypeConfig) -> Dict:
        """Build database query filters."""
        filters = {
            "docstatus": 1,
            "company": args["company"],
            **config.additional_filters
        }

        if args.get("party"):
            filters["employee"] = args["party"]
        
        self._add_date_filter(filters, config.date_field, args.get("from_posting_date"), args.get("to_posting_date"))

        due_date_field = "due_date" if args["transaction_to_pay_against"] == "Purchase Invoice" else "schedule_date"
        self._add_date_filter(filters, due_date_field, args.get("from_due_date"), args.get("to_due_date"))

        if greater_than := args.get("outstanding_amt_greater_than"):
            filters["outstanding_amount"] = [">", greater_than]
        if less_than := args.get("outstanding_amt_less_than"):
            if greater_than:
                filters["outstanding_amount"] = ["between", [greater_than, less_than]]
            else:
                filters["outstanding_amount"] = ["<", less_than]

        return filters

    def _add_date_filter(self, filters: Dict, field: str, from_date: Optional[str], to_date: Optional[str]) -> None:
        """
        Add date range filter to filters dictionary.

        Args:
            filters: Dictionary to update with date filters.
            field: Field name for the date filter.
            from_date: Start date for the filter.
            to_date: End date for the filter.
        """

        if from_date and to_date:
            filters[field] = ["between", [from_date, to_date]]
        elif from_date:
            filters[field] = [">=", from_date]
        elif to_date:
            filters[field] = ["<=", to_date]

    def _fetch_entries(self, doctype: str, config: DoctypeConfig, args: Dict, filters: Dict) -> List[Dict]:
        """
        Fetch documents from database.
        
        Args:
            doctype: Document type to fetch.
            config: Doctype configuration.
            args: Filter parameters.
            filters: Database query filters

        Returns:
            List of document entries.
        """
        if config.use_erpnext_function:
            return self._fetch_erpnext_entries(doctype, args)

        try:
            entries = frappe.db.get_all(
                doctype,
                filters=filters,
                fields=config.fields or [],
                order_by=f"{config.date_field} asc",
                limit=1000
            )
        except Exception as e:
            frappe.log_error(f"Error fetching {doctype}: {str(e)}", "Error Fetching Entries")
            frappe.msgprint(
                _(f"Failed to fetch {doctype} references"),
                title=_("Error"),
                indicator="red"
            )
            return []
        
        if doctype == "Employee Advance":
            entries = [e for e in entries if (e.paid_amount or 0) < (e.advance_amount or 0)]

        if not entries:
            frappe.msgprint(
                _(f"No outstanding references found for the set filters"),
                title=_("No References"),
                indicator="blue"
            )
    
        return entries

    def _fetch_erpnext_entries(self, doctype: str, args: Dict) -> List[Dict]:
        """
        Fetch entries using ERPNext's function for specific doctypes.

        Args:
            doctype: Document type to fetch.
            args: Filter parameters.

        Returns:
            List of document entries.
        """
        party_type = args.get("party_type")
        company = args.get("company")
        party = args.get("party")
        parties = [party] if party else frappe.get_all(party_type, filters={"disabled": 0}, pluck="name")
        
        # Batch fetch party accounts
        party_accounts = {}
        for p in parties:
            try:
                accounts = get_party_account(
                    party_type, p, company,
                    include_advance=args.get("book_advance_payments_in_separate_party_account", False)
                )
                party_accounts[p] = accounts[0] if isinstance(accounts, list) else accounts
            except Exception as e:
                app_logger.error(f"Failed fetching account for {party_type} {p}: {str(e)}")
        
        all_entries = []
        for party in parties:
            if not (party_account := party_accounts.get(party)):
                continue
            
            erpnext_args = {
                "party_type": party_type,
                "party": party,
                "company": company,
                "party_account": party_account,
                "get_outstanding_invoices": doctype == "Purchase Invoice",
                "get_orders_to_be_billed": doctype == "Purchase Order",
                "from_posting_date": args.get("from_posting_date"),
                "to_posting_date": args.get("to_posting_date"),
                "from_due_date": args.get("from_due_date"),
                "to_due_date": args.get("to_due_date"),
                "outstanding_amt_greater_than": args.get("outstanding_amt_greater_than"),
                "outstanding_amt_less_than": args.get("outstanding_amt_less_than"),
                "book_advance_payments_in_separate_party_account": args.get("book_advance_payments_in_separate_party_account", False)
            }

            try:
                entries = original_get_outstanding_reference_documents(erpnext_args)
                entries = [e for e in entries if e["voucher_type"] == doctype]
                for entry in entries:
                    entry["party"] = party
                    entry["party_type"] = party_type
                all_entries.extend(entries)
            except Exception as e:
                app_logger.error(f"Failed fetching for {party_type} {party}: {str(e)}")
        
        return all_entries
    
    def _populate_references(self, entries: List[Dict], args: Dict, doctype: str, date_field: str) -> List[Dict]:
        """Process entries and populate the references child table."""
        if not entries:
            return []

        # Clear existing references
        self.set("references", [])
        references = []
        config = self._get_doctype_config(doctype)

        for entry in entries:
            payable_amount = config.payable_amount_calc(entry)
            if payable_amount <= 0:
                app_logger.info(f"Skipping entry due to zero or negative payable amount: {entry}")
                continue

            if not (party_info := self._extract_party_info(entry, args)):
                frappe.log_error(title="Skipping Entry", message=f"Skipping entry due to missing party or party_type: {entry}")

            party, party_type = party_info["party"], party_info["party_type"]            

            # Get phone number (required field)
            partyb = self.get_party_phone(entry, party_type)
            if not partyb:
                frappe.log_error(title=f"Missing Phone - {party}"[:140], message=f"Skipping entry due to missing phone number for {party}: {entry}", )

            currency = entry.get("currency") or self.company_currency
            if not entry.get("currency"):
                app_logger.warning(f"Currency not found for {doctype} {entry.get('name')}")

            reference = {
                "reference_doctype": doctype,
                "reference_name": entry.get("voucher_no") or entry.get("name"),
                "party_type": party_type,
                "party": party,
                "due_date": entry.get("due_date") or entry.get("schedule_date"),
                "total_amount": self._get_invoice_amount(entry, config),
                "outstanding_amount": payable_amount,
                "allocated_amount": 0,
                "currency":currency,
                "exchange_rate": self._get_exchange_rate(entry, doctype),
                "partyb": partyb,
                "payment_status": "Not Initiated",
                "originator_conversation_id": self._generate_uuid_v4()
            }
            references.append(reference)

            self.append("references", {
                "reference_doctype": reference["reference_doctype"],
                "reference_name": reference["reference_name"],
                "party_type": reference["party_type"],
                "party": reference["party"],
                "due_date": reference["due_date"],
                "total_amount": reference["total_amount"],
                "outstanding_amount": reference["outstanding_amount"],
                "allocated_amount": reference["allocated_amount"],
                "currency": reference["currency"],
                "exchange_rate": reference["exchange_rate"],
                "partyb": reference["partyb"],
            })

        return references

    def _extract_party_info(self, entry: Dict, args: Dict) -> Optional[Dict]:
        """Extract party and party_type from entry or args."""

        party = entry.get("party") or entry.get("employee") or entry.get("supplier")
        party_type = entry.get("party_type") or args.get("party_type")
        
        if not party or not party_type:
            app_logger.info(f"Skipping entry due to missing party or party_type: {entry}")
            return None
        
        return {"party": party, "party_type": party_type}

    def _get_invoice_amount(self, entry: Dict, config: DoctypeConfig) -> float:
        """
        Calculate invoice amount based on document type.

        Args:
            entry: Document entry.
            config: Doctype configuration.

        Returns:
            Invoice amount.
        """
        return entry.get(config.invoice_amount_field, 0)

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

    @frappe.whitelist()
    def allocate_amount_to_references(self, paid_amount, paid_amount_change=0, allocate_payment_amount=None):
        if not self.references:
            return

        allocate_payment_amount = allocate_payment_amount if allocate_payment_amount is not None else frappe.flags.allocate_payment_amount or False

        if not allocate_payment_amount:
            for ref in self.references:
                ref.allocated_amount = 0
            return
        
        precision = self.precision("paid_amount")
        total_positive_outstanding = 0
        total_negative_outstanding = 0
        paid_amount = flt(paid_amount, precision)

        for ref in self.references:
            outstanding_amount = flt(ref.outstanding_amount, precision)
            if outstanding_amount > 0:
                total_positive_outstanding += outstanding_amount
            else:
                total_negative_outstanding -= abs(outstanding_amount)

        allocated_positive_outstanding = 0
        allocated_negative_outstanding = 0

        if total_positive_outstanding > paid_amount:
            remaining_outstanding = flt(total_positive_outstanding - paid_amount, precision)
            allocated_negative_outstanding = min(remaining_outstanding, total_negative_outstanding)
        allocated_positive_outstanding = paid_amount + allocated_negative_outstanding

        for ref in self.references:
            outstanding_amount = flt(ref.outstanding_amount, precision)
            if outstanding_amount > 0 and allocated_positive_outstanding >= 0:
                ref.allocated_amount = min(allocated_positive_outstanding, outstanding_amount)
                allocated_positive_outstanding = flt(allocated_positive_outstanding - ref.allocated_amount, precision)
            elif outstanding_amount < 0 and allocated_negative_outstanding > 0:
                ref.allocated_amount = min(allocated_negative_outstanding, abs(outstanding_amount)) * -1
                allocated_negative_outstanding = flt(allocated_negative_outstanding - abs(ref.allocated_amount), precision)
            else:
                ref.allocated_amount = 0
