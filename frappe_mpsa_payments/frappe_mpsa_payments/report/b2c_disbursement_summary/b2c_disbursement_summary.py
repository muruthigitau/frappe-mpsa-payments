# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt

# import frappe


def execute(filters=None):
    columns = get_columns()
    columns = get_data(filters)

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
            "width": 150,
        },
        {
            "fieldname": "company",
            "fieldtype": "Link",
            "label": "Company",
            "options": "Company",
            "width": 150,
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
            "fieldname": "party",
            "fieldtype": "Data",  # TODO: Change to Link if needed
            "label": "Party",
            "width": 150,
        },
        {
			"fieldname": "party_type",
			"fieldtype": "Data",  # TODO: Change to Link if needed
			"label": "Party Type",
			"width": 150,
		}
    ]
