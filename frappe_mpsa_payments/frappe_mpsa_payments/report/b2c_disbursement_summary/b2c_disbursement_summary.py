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
            "fieldtype": "Link",  # TODO: Change to Link if needed
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
    query = """
		SELECT
			d.name,
			d.payment_type,
			d.posting_date,
			d.company,
			d.mode_of_payment,
			d.transaction_to_pay_against,
			r.total_amount,
			r.currency,
			r.party,
			r.party_type
		FROM
			`tabB2C Payment Disbursement` d
		LEFT JOIN
			`tabB2C Payment Disbursement Reference` r
		ON
			d.name = r.parent
	"""
    data = frappe.db.sql(query, as_dict=True)
    return data
