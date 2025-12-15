import frappe
from frappe.utils import nowdate

from frappe_mpsa_payments.frappe_mpsa_payments.api.payment_entry import (
    create_payment_entry,
)


def create_payment_entry_for_doc(b2c_disbursement, b2c_disbursement_ref, submit=False):
    """
    Create a Payment Entry for various reference doctypes.

    Args:
        b2c_disbursement: B2C Payment Disbursement document
        b2c_disbursement_ref: B2C Payment Disbursement Reference document
        submit: whether to submit the Payment Entry
    """
    import erpnext

    current_user = frappe.session.user
    frappe.set_user("Administrator")

    try:
        # Gather parameters
        party_type = b2c_disbursement_ref.party_type
        party_account = b2c_disbursement.paid_to
        party = frappe.db.get_value(party_type, b2c_disbursement_ref.party, "name")
        amount = b2c_disbursement_ref.allocated_amount
        company = b2c_disbursement.company
        currency = frappe.db.get_value("Company", company, "default_currency")
        mode_of_payment = b2c_disbursement.mode_of_payment
        reference_date = b2c_disbursement_ref.reference_date
        reference_no = b2c_disbursement_ref.reference_no

        references = [
            {
                "reference_doctype": b2c_disbursement_ref.reference_doctype,
                "reference_name": b2c_disbursement_ref.reference_name,
                "allocated_amount": amount,
                "b2c_payment_disbursement": b2c_disbursement.name,
            }
        ]

        create_payment_entry(
            company,
            party,
            amount,
            currency,
            mode_of_payment,
            party_type=party_type,
            reference_date=reference_date,
            reference_no=reference_no,
            posting_date=nowdate(),
            cost_center=erpnext.get_default_cost_center(company),
            submit=submit,
            references=references,
            party_account=party_account,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Payment Entry Service Error")
    finally:
        frappe.set_user(current_user)
