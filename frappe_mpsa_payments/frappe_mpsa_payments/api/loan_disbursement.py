import frappe

from lending.loan_management.doctype.loan.loan import make_loan_disbursement

def create_loan_disbursement(b2c_disbursement, b2c_disbursement_ref):
    try:
        loan = frappe.get_doc("Loan", b2c_disbursement_ref.reference_name)

        disbursement_entry = make_loan_disbursement(
            loan=loan.name,
            company=loan.company,
            applicant_type=loan.applicant_type,
            applicant=loan.applicant,
            pending_amount=b2c_disbursement_ref.allocated_amount
        )

        disbursement_entry.insert(ignore_permissions=True)
        # disbursement_entry.submit()

        frappe.db.commit()

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Loan Disbursement Creation Failed")