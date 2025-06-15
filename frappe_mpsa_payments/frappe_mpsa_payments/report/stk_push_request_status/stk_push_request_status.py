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
            "fieldname": "transaction_id",
            "fieldtype": "Data",
            "label": "Request ID",
            "width": 150,
        },
        {
            "fieldname": "timestamp",
            "fieldtype": "Datetime",
            "label": "Transaction Date",
            "width": 180,
        },
        {
            "fieldname": "phone_number",
            "fieldtype": "Data",
            "label": "Phone Number",
            "width": 150,
        },
        {
            "fieldname": "amount",
            "fieldtype": "Currency",
            "label": "Amount",
            "width": 150,
        },
        {
            "fieldname": "merchant_request_id",
            "fieldtype": "Data",
            "label": "Merchant Request ID",
            "width": 180,
        },
        {
            "fieldname": "checkout_request_id",
            "fieldtype": "Data",
            "label": "Checkout Request ID",
            "width": 180,
        },
        {
            "fieldname": "error_message",
            "fieldtype": "Data",
            "label": "Error Message",
            "width": 200,
        },
        {
            "fieldname": "status",
            "fieldtype": "Data",
            "label": "Status",
            "width": 150,
        },
    ]


def get_conditions(filters):
    conditions = []
    values = {}

    if filters.get("status"):
        conditions.append("status = %(status)s")
        values["status"] = filters["status"]

    if filters.get("start_date"):
        conditions.append("timestamp >= %(start_date)s")
        values["start_date"] = filters["start_date"]

    if filters.get("end_date"):
        conditions.append("timestamp <= %(end_date)s")
        values["end_date"] = filters["end_date"]

    if filters.get("phone_number"):
        conditions.append("phone_number = %(phone_number)s")
        values["phone_number"] = filters["phone_number"]

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else "1=1"

    return where_clause, values


def get_data(filters):
    where_clause, values = get_conditions(filters)

    query = f"""
        SELECT
            name as transaction_id,
            amount,
            phone_number,
            status,
            timestamp,
            account_reference as merchant_request_id,
            name as checkout_request_id,
               checkout_request_id,
            result_desc as error_message
        FROM `tabMpesa Express Request`
        {where_clause}
        ORDER BY timestamp DESC
    """

    return frappe.db.sql(query, values, as_dict=True)
