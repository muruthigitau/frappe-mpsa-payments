# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    # This function returns the columns to be displayed in the report
    return [
        {
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "label": "Posting Date",
            "width": 150,
        },
        {
            "fieldname": "transactiontype",
            "fieldtype": "Data",
            "label": "Transaction Type",
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
            "fieldname": "transid",
            "fieldtype": "Data",
            "label": "Trans ID",
            "width": 150,
        },
        {
            "fieldname": "transtime",
            "fieldtype": "Data",
            "label": "Trans Time",
            "width": 150,
        },
        {
            "fieldname": "transamount",
            "fieldtype": "Float",
            "label": "Trans Amount",
            "width": 150,
        },
        {
            "fieldname": "docstatus",
            "fieldtype": "Int",
            "label": "Docstatus",
            "width": 100,
        },
        {
            "fieldname": "payment_entry",
            "fieldtype": "Link",
            "label": "Payment Entry",
            "options": "Payment Entry",
            "width": 180,
        },
    ]


def get_data(filters):
    where_clause, values = get_conditions(filters or {})

    query = f"""
        SELECT
            posting_date,
            transactiontype,
            company,
            transid,
            transtime,
            transamount
        FROM
            `tabMpesa C2B Payment Register`
        WHERE
            {where_clause}
        ORDER BY
            posting_date DESC
    """

    # TODO: Remove this print statement
    print("Executing query:", query)

    data = frappe.db.sql(query, values, as_dict=True)
    return data


def get_conditions(filters):
    conditions = []
    values = {}

    # Posting Date filter
    if filters.get("posting_date"):
        print("Applying posting_date filter:", filters["posting_date"])
        conditions.append("posting_date = %(posting_date)s")
        print("Filter conditions:", conditions)
        values["posting_date"] = filters["posting_date"]

    # Status filter (Draft/Submitted/Cancelled)
    if filters.get("status"):
        print("Applying status filter:", filters["status"])
        status_map = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
        docstatus = status_map.get(filters["status"])
        if docstatus is not None:
            conditions.append("docstatus = %(docstatus)s")
            values["docstatus"] = docstatus

    # Unlinked Mpesa Payments filter
    if filters.get("unlinked_mpesa_payments"):
        conditions.append("(payment_entry IS NULL OR payment_entry = '')")

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    return where_clause, values
