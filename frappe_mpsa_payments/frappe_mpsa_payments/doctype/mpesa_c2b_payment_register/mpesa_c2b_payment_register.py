# # Copyright (c) 2024, Navari Limited and contributors
# # For license information, please see license.txt

# import frappe
# from frappe import _
# from frappe.model.document import Document
# from frappe_mpsa_payments.frappe_mpsa_payments.api.payment_entry import create_payment_entry, get_outstanding_invoices, get_unallocated_payments, create_and_reconcile_payment_reconciliation
# from django.db.models.signals import pre_save, post_save
# from django.dispatch import receiver
# from .models import MpesaC2BPaymentRegister
# from .api.payment_entry import create_payment_entry, create_and_reconcile_payment_reconciliation
# from django.core.exceptions import ValidationError

# class MpesaC2BPaymentRegister(Document):
#     def before_insert(self):
#         self.set_missing_values()

#     def set_missing_values(self):
#         self.currency = "KES"
#         self.full_name = ""
#         if self.firstname:
#             self.full_name = self.firstname
#         if self.middlename:
#             self.full_name += " " + self.middlename
#         if self.lastname:
#             self.full_name += " " + self.lastname

#         register_url_list = frappe.get_all(
#             "Mpesa C2B Payment Register URL",
#             filters={
#                 "business_shortcode": self.businessshortcode,
#                 "register_status": "Success",
#             },
#             fields=["company", "mode_of_payment"],
#         )
#         if len(register_url_list) > 0:
#             self.company = register_url_list[0].company
#             self.mode_of_payment = register_url_list[0].mode_of_payment

#     def before_submit(self):
#         if not self.transamount:
#             frappe.throw(_("Trans Amount is required"))
#         if not self.company:
#             frappe.throw(_("Company is required"))
#         if not self.customer:
#             frappe.throw(_("Customer is required"))
#         if not self.mode_of_payment:
#             frappe.throw(_("Mode of Payment is required"))
#         if self.submit_payment:
#            self.payment_entry = self.create_payment_entry()

#     def create_payment_entry(self):
#         payment_entry = create_payment_entry(
#             self.company,
#             self.customer,
#             self.transamount,
#             self.currency,
#             self.mode_of_payment,
#             self.posting_date,

#             self.name,
#             self.posting_date,
            
#             None,
#             self.submit_payment,
#         )
#         return payment_entry.name
    
#     def on_submit(self):

#         try:
#             matching_invoice = frappe.get_value(
#                 "Sales Invoice",
#                 {"name": self.billrefnumber, "docstatus": 1, "company": self.company, "customer": self.customer, "outstanding_amount": (">", 0)},
#                 "name"
#             )

#             if matching_invoice:
#                 create_and_reconcile_payment_reconciliation(
#                     outstanding_invoices=[matching_invoice],
#                     customer=self.customer,
#                     company=self.company,
#                     payment_entries=[self.payment_entry]
#                 )
            
#             frappe.response["http_status_code"] = 200

#         except Exception as e:
#             frappe.log_error(frappe.get_traceback(), str(e))
#             @receiver(pre_save, sender=MpesaC2BPaymentRegister)
#             def set_missing_values(sender, instance, **kwargs):
#                 instance.currency = "KES"
#                 instance.full_name = ""
#                 if instance.firstname:
#                     instance.full_name = instance.firstname
#                 if instance.middlename:
#                     instance.full_name += " " + instance.middlename
#                 if instance.lastname:
#                     instance.full_name += " " + instance.lastname

#                 register_url_list = MpesaC2BPaymentRegisterURL.objects.filter(
#                     business_shortcode=instance.businessshortcode,
#                     register_status="Success"
#                 ).values("company", "mode_of_payment")
#                 if register_url_list.exists():
#                     instance.company = register_url_list[0]["company"]
#                     instance.mode_of_payment = register_url_list[0]["mode_of_payment"]

#             @receiver(pre_save, sender=MpesaC2BPaymentRegister)
#             def validate_before_submit(sender, instance, **kwargs):
#                 if instance.pk is None:  # Only validate on creation
#                     if not instance.transamount:
#                         raise ValidationError("Trans Amount is required")
#                     if not instance.company:
#                         raise ValidationError("Company is required")
#                     if not instance.customer:
#                         raise ValidationError("Customer is required")
#                     if not instance.mode_of_payment:
#                         raise ValidationError("Mode of Payment is required")
#                     if instance.submit_payment:
#                         instance.payment_entry = create_payment_entry(
#                             instance.company,
#                             instance.customer,
#                             instance.transamount,
#                             instance.currency,
#                             instance.mode_of_payment,
#                             instance.posting_date,
#                             instance.name,
#                             instance.posting_date,
#                             None,
#                             instance.submit_payment,
#                         ).name

#             @receiver(post_save, sender=MpesaC2BPaymentRegister)
#             def reconcile_payment_on_submit(sender, instance, created, **kwargs):
#                 if created and instance.submit_payment:
#                     try:
#                         matching_invoice = SalesInvoice.objects.filter(
#                             name=instance.billrefnumber,
#                             docstatus=1,
#                             company=instance.company,
#                             customer=instance.customer,
#                             outstanding_amount__gt=0
#                         ).values("name").first()

#                         if matching_invoice:
#                             create_and_reconcile_payment_reconciliation(
#                                 outstanding_invoices=[matching_invoice["name"]],
#                                 customer=instance.customer,
#                                 company=instance.company,
#                                 payment_entries=[instance.payment_entry]
#                             )
#                     except Exception as e:
#                         logger.error(f"Error during payment reconciliation: {str(e)}")