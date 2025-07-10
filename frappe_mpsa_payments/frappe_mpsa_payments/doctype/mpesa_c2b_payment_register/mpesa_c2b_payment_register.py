# Copyright (c) 2024, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe_mpsa_payments.frappe_mpsa_payments.api.payment_entry import create_payment_entry, get_outstanding_invoices, get_unallocated_payments, create_and_reconcile_payment_reconciliation

class MpesaC2BPaymentRegister(Document):
	def before_insert(self):
		self.set_missing_values()

	def after_insert(self):
		try:
			auto_reconcile = frappe.db.get_value(
				"Mpesa Settings",
				{"business_shortcode": self.businessshortcode},
				"auto_reconcile_c2b",
			)

			if not auto_reconcile:
				return
			
			self.db_set("submit_payment", 1)
			self.submit()
		
		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"C2B Auto-submit Error: {str(e)}")

	def set_missing_values(self):
		self.currency = "KES"
		self.full_name = self.full_name = " ".join(filter(None, [self.firstname, self.middlename, self.lastname]))

		register_url_list = frappe.get_all(
			"Mpesa C2B Payment Register URL",
			filters={
				"business_shortcode": self.businessshortcode,
				"register_status": "Success",
			},
			fields=["company", "mode_of_payment"],
		)
		if len(register_url_list) > 0:
			self.company = register_url_list[0].company
			self.mode_of_payment = register_url_list[0].mode_of_payment

		if self.billrefnumber and not self.customer:
			self._find_customer_from_billref(self.billrefnumber)        

	def before_submit(self):
		if not self.transamount:
			frappe.throw(_("Trans Amount is required"))
		if not self.company:
			frappe.throw(_("Company is required"))
		if not self.customer:
			frappe.throw(_("Customer is required"))
		if not self.mode_of_payment:
			frappe.throw(_("Mode of Payment is required"))
			

		if self.submit_payment:
			
			refs = []
			invoice, order = self._get_matching_refs()

			if invoice:
				refs.append({"reference_doctype": "Sales Invoice", "reference_name": invoice, "allocated_amount": self.transamount})
			
			elif order:
				refs.append({"reference_doctype": "Sales Order", "reference_name": order, "allocated_amount": self.transamount})

			payment_entry = create_payment_entry(
				self.company,
				self.customer,
				self.transamount,
				self.currency,
				self.mode_of_payment,
				"Customer",
				self.posting_date,
				self.name,
				self.posting_date,
				None,
				self.submit_payment,
				references=refs or None
			)

			self.payment_entry = payment_entry.name
			   
	def on_submit(self):

		try:
			self._reconcile_payment()

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"C2B Reconciliation Error: {str(e)}")

	def _find_customer_from_billref(self, billrefnumber: str) -> str | None:

		if not billrefnumber:
			return

		sources = [
			("Sales Invoice", "customer", {"docstatus": 1}),
			("Sales Order", "customer", {"docstatus": 1}),
			("Quotation", "party_name", {"docstatus": 1, "quotation_to": "Customer"}),
			("Customer", "name", {})
		]

		for doctype, customer_field, extra_filters in sources:
			filters = {"name": billrefnumber}
			filters.update(extra_filters)

			customer = frappe.db.get_value(
				doctype,
				filters,
				customer_field
			)
			if customer:
				self.customer = customer
				return
			
	def _reconcile_payment(self):
		settings = frappe.get_cached_value(
			"Mpesa Settings", {"business_shortcode": self.businessshortcode},
			["auto_reconcile_c2b", "auto_create_sales_invoice"],
			as_dict=True,
		)

		if not settings.auto_reconcile_c2b or not self.payment_entry:
			return

		invoice, order = self._get_matching_refs()
		
		if order and settings.auto_create_sales_invoice:
			self._create_sales_invoice_from_order(order)

		else:

			# Fallback: FIFO
			outstanding_invoices = get_outstanding_invoices(
				customer=self.customer, company=self.company
			)

			if outstanding_invoices:
				self._reconcile_against_invoice(outstanding_invoices)


	def _get_matching_refs(self):
		"""
		Returns a tuple (invoice, sales_order), where exactly one is non-None if billrefnumber matched either.
		Otherwise both are None.
		"""
		invoice = self._find_matching_invoice()
		if invoice:
			return invoice, None
		
		order = self._find_matching_sales_order()
		if order:
			return None, order
		
		return None, None
	

	def _find_matching_invoice(self):
		if not self.billrefnumber:
			return None

		return frappe.get_value(
			"Sales Invoice",
			{
				"name": self.billrefnumber,
				"docstatus": 1,
				"company": self.company,
				"customer": self.customer,
				"outstanding_amount": (">", 0),
			},
			"name"
		)

	def _find_matching_sales_order(self):
		if not self.billrefnumber:
			return None

		return frappe.get_value(
			"Sales Order",
			{
				"name": self.billrefnumber,
				"docstatus": 1,
				"company": self.company,
				"customer": self.customer,
				"status": ("not in", ["Closed", "Completed"]),
			},
			"name"
		)

	def _create_sales_invoice_from_order(self, sales_order):
		try:
			from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice

			si = make_sales_invoice(sales_order)
			# si.allocate_advances_automatically = True
			si.insert(ignore_permissions=True)
			si.submit()

			return si.name

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"Sales Invoice Creation Failed for SO {sales_order}")
			return None

	def _reconcile_against_invoice(self, invoice_list):
		if isinstance(invoice_list, str):
			invoice_list = [invoice_list]

		create_and_reconcile_payment_reconciliation(
			outstanding_invoices=invoice_list,
			customer=self.customer,
			company=self.company,
			payment_entries=[self.payment_entry],
		)
