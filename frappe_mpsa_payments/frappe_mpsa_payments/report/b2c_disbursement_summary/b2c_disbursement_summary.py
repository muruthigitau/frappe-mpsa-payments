import frappe
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "label": "Posting Date",
            "width": 120,
        },
        {
            "fieldname": "name",
            "fieldtype": "Link",
            "label": "Disbursement",
            "options": "B2C Payment Disbursement",
            "width": 250,
        },
        {
            "fieldname": "mode_of_payment",
            "fieldtype": "Link",
            "label": "Mode of Payment",
            "options": "Mode of Payment",
            "width": 250,
        },
        {
            "fieldname": "transaction_to_pay_against",
            "fieldtype": "Link",
            "label": "Transaction to Pay Against",
            "options": "DocType",
            "width": 150,
        },
        {
            "fieldname": "party_type",
            "fieldtype": "Link",
            "label": "Party Type",
            "options": "Party Type",
            "width": 100,
        },
        {
            "fieldname": "party",
            "fieldtype": "Data",
            "label": "Party",
            "width": 150,
        },
        {
            "fieldname": "currency",
            "fieldtype": "Link",
            "label": "Currency",
            "options": "Currency",
            "width": 100,
        },
        {
            "fieldname": "total_amount",
            "fieldtype": "Currency",
            "label": "Amount",
            "width": 120,
        },
        {"fieldname": "status", "fieldtype": "Data", "label": "Status", "width": 100},
    ]


def get_data(filters):
    """Fetches data for the B2C Disbursement Summary report based on the provided filters."""
    Disbursement = frappe.qb.DocType("B2C Payment Disbursement")
    Reference = frappe.qb.DocType("B2C Payment Disbursement Reference")

    final_report_data = []
    disbursement_names = []

    disbursement_query = frappe.qb.from_(Disbursement).select(
        Disbursement.name,
        Disbursement.posting_date,
        Disbursement.company,
        Disbursement.mode_of_payment,
        Disbursement.transaction_to_pay_against,
        Disbursement.status,
        Disbursement.payment_type,
    )

    disbursement_query = apply_disbursement_filters(
        disbursement_query, filters, Disbursement
    )
    disbursements_list = disbursement_query.run(as_dict=True)

    disbursements_map = {d.name: d for d in disbursements_list}
    disbursement_names = list(disbursements_map.keys())

    if not disbursement_names:
        return []

    references_query = (
        frappe.qb.from_(Reference)
        .select(
            Reference.parent,
            Reference.total_amount,
            Reference.currency,
            Reference.party,
            Reference.party_type,
        )
        .where(Reference.parent.isin(disbursement_names))
    )

    if filters.get("party_type"):
        references_query = references_query.where(
            Reference.party_type == filters["party_type"]
        )

    all_references = references_query.run(as_dict=True)

    grouped_references = {}
    for ref in all_references:
        grouped_references.setdefault(ref.parent, []).append(ref)

    for disburse_name in sorted(disbursements_map.keys()):
        disburse = disbursements_map[disburse_name]
        current_disbursement_references = grouped_references.get(disburse.name, [])
        current_disbursement_subtotal = 0.0

        final_report_data.append(
            {
                "posting_date": disburse.posting_date,
                "name": disburse.name,
                "company": disburse.company,
                "mode_of_payment": disburse.mode_of_payment,
                "transaction_to_pay_against": disburse.transaction_to_pay_against,
                "total_amount": None,
                "currency": None,
                "party_type": None,
                "party": None,
                "status": disburse.status,
            }
        )

        for ref in current_disbursement_references:
            final_report_data.append(
                {
                    "posting_date": disburse.posting_date,
                    "name": disburse.name,
                    "company": disburse.company,
                    "mode_of_payment": disburse.mode_of_payment,
                    "transaction_to_pay_against": disburse.transaction_to_pay_against,
                    "status": disburse.status,
                    "total_amount": flt(ref.total_amount),
                    "currency": ref.currency,
                    "party_type": ref.party_type,
                    "party": ref.party,
                }
            )
            current_disbursement_subtotal += flt(ref.total_amount)

        if current_disbursement_references:
            final_report_data.append(
                {
                    "is_subtotal": True,
                    "posting_date": None,
                    "name": f"{disburse.name}",
                    "company": None,
                    "mode_of_payment": None,
                    "transaction_to_pay_against": None,
                    "currency": None,
                    "total_amount": current_disbursement_subtotal,
                    "party_type": None,
                    "party": None,
                    "status": None,
                    "bold": True,
                }
            )
            final_report_data.append({})

    return final_report_data


def apply_disbursement_filters(query, filters, Disbursement):
    """Applies filters relevant to the B2C Payment Disbursement doctype."""
    if filters:
        if filters.get("start_date"):
            query = query.where(Disbursement.posting_date >= filters["start_date"])
        if filters.get("end_date"):
            query = query.where(Disbursement.posting_date <= filters["end_date"])
        if filters.get("company"):
            query = query.where(Disbursement.company == filters["company"])
        if filters.get("mode_of_payment"):
            query = query.where(
                Disbursement.mode_of_payment == filters["mode_of_payment"]
            )
        if filters.get("status"):
            query = query.where(Disbursement.status == filters["status"])

    return query
