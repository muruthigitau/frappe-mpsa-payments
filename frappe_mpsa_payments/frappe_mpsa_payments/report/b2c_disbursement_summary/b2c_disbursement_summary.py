# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt

import frappe


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
            "fieldname": "company",
            "fieldtype": "Link",
            "label": "Company",
            "options": "Company",
            "width": 250,
        },
        {
            "fieldname": "mode_of_payment",
            "fieldtype": "Link",
            "label": "Mode of Payment",
            "options": "Mode of Payment",
            "width": 150,
        },
        {
            "fieldname": "transaction_to_pay_against",
            "fieldtype": "Link",
            "label": "Transaction to Pay Against",
            "options": "DocType",
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
        {
            "fieldname": "party_type",
            "fieldtype": "Link",
            "label": "Party Type",
            "options": "Party Type",
            "width": 100,
        },
        {
            "fieldname": "party",
            "fieldtype": "Data",  # TODO: Change to Link if needed
            "label": "Party",
            "width": 150,
        },
        {"fieldname": "status", "fieldtype": "Data", "label": "Status", "width": 100},
    ]


def get_data(filters):
    Disbursement = frappe.qb.DocType("B2C Payment Disbursement")
    Reference = frappe.qb.DocType("B2C Payment Disbursement Reference")

    query = (
        frappe.qb.from_(Disbursement)
        .left_join(Reference)
        .on(Disbursement.name == Reference.parent)
        .select(
            Disbursement.name.as_("name"),
            Disbursement.payment_type.as_("payment_type"),
            Disbursement.posting_date.as_("posting_date"),
            Disbursement.company.as_("company"),
            Disbursement.mode_of_payment.as_("mode_of_payment"),
            Disbursement.transaction_to_pay_against.as_("transaction_to_pay_against"),
            Disbursement.status.as_("status"),
            Reference.total_amount.as_("total_amount"),
            Reference.currency.as_("currency"),
            Reference.party.as_("party"),
            Reference.party_type.as_("party_type"),
        )
    )

    query = apply_filters(query, filters, Disbursement, Reference)

    data = query.run(as_dict=True)

    return data


def apply_filters(query, filters, Disbursement, Reference):
    if filters:
        if filters.get("start_date"):
            query = query.where(Disbursement.posting_date >= filters["start_date"])
        if filters.get("end_date"):
            query = query.where(Disbursement.posting_date <= filters["end_date"])
        if filters.get("company"):
            query = query.where(Disbursement.company == filters["company"])
        if filters.get("party_type"):
            query = query.where(Reference.party_type == filters["party_type"])
    return query
