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
            "label": "Customer",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 200,
        },
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 200,
        },
        {
            "label": "Total Amount",
            "fieldname": "total_amount",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Payment Count",
            "fieldname": "payment_count",
            "fieldtype": "Int",
            "width": 120,
        },
    ]


def get_data(filters):
    where_clause, values = get_filters(filters)

    data = frappe.db.sql(
        f"""
        SELECT
            customer,
            MAX(customer) as customer_name,
            SUM(transamount) as total_amount,
            COUNT(name) as payment_count
        FROM `tabMpesa C2B Payment Register`
        WHERE {where_clause}
        GROUP BY customer
        ORDER BY posting_date DESC
    """,
        values,
        as_dict=True,
    )

    return data


def get_filters(filters):
    conditions = []
    values = {}

    if filters.get("start_date"):
        conditions.append("posting_date >= %(start_date)s")
        values["start_date"] = filters["start_date"]

    if filters.get("end_date"):
        conditions.append("posting_date <= %(end_date)s")
        values["end_date"] = filters["end_date"]

    if filters.get("company"):
        conditions.append("company = %(company)s")
        values["company"] = filters["company"]

    if filters.get("status"):
        status_map = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
        docstatus = status_map.get(filters["status"])
        if docstatus is not None:
            conditions.append("docstatus = %(docstatus)s")
            values["docstatus"] = docstatus

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # TODO: Delete this line when the report is ready
    print(f"Where clause received: {where_clause}, Values: {values}")

    return where_clause, values
