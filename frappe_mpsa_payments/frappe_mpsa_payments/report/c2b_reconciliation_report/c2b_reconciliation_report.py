# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)

    # TODO: Delete this print statement after debugging
    for row in data:
        print("Status row: ", row["status"])
        print("Payment Entry row: ", row.get("payment_entry", "No Payment Entry"))

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
            "fieldname": "transamount",
            "fieldtype": "Float",
            "label": "Trans Amount",
            "width": 150,
        },
        {
            "fieldname": "payment_entry",
            "fieldtype": "Link",
            "label": "Payment Entry",
            "options": "Payment Entry",
            "width": 180,
        },
        {
            "fieldname": "status",
            "fieldtype": "Data",
            "label": "Status",
            "width": 100,
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
            transamount,
            payment_entry,
            docstatus
        FROM
            `tabMpesa C2B Payment Register`
        WHERE
            {where_clause}
        ORDER BY
            posting_date DESC
    """

    data = frappe.db.sql(query, values, as_dict=True)

    # Map docstatus values to human-readable strings
    status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

    for row in data:
        row["docstatus"] = status_map.get(row["docstatus"], "Unknown")
        print("Docstatus row should show: ", row["docstatus"])
        row["status"] = row["docstatus"]

        # print("Status field should show: ", row["status"])
        payment_entry = row.get("payment_entry", "None")
        # print("Payment Entry: ", row.get("payment_entry", "No Payment Entry"))

    return data


def get_conditions(filters):
    conditions = []
    values = {}

    # Posting Date filter
    if filters.get("posting_date"):
        conditions.append("posting_date >= %(posting_date)s")
        values["posting_date"] = filters["posting_date"]

    # Status filter (Draft/Submitted/Cancelled)
    if filters.get("status"):
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
