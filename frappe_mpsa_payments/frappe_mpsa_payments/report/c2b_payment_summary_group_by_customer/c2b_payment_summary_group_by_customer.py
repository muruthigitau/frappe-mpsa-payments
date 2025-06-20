# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import DocType
from pypika.terms import Criterion
from pypika.functions import Sum, Count, Max


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
            "label": "Transaction ID",
            "fieldname": "transid",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Posting Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Amount",
            "fieldname": "transamount",
            "fieldtype": "Currency",
            "width": 120,
        },
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
    ]


def get_data(filters):
    MpesaC2B = DocType("Mpesa C2B Payment Register")

    # Base query (no grouping) to get individual payment rows
    query = (
        frappe.qb.from_(MpesaC2B)
        .select(
            MpesaC2B.customer,
            MpesaC2B.full_name.as_("customer_name"),
            MpesaC2B.transamount,
            MpesaC2B.docstatus,
        )
        .where(MpesaC2B.customer.isnotnull())
        .orderby(MpesaC2B.customer, order=frappe.qb.asc)
        .orderby(MpesaC2B.posting_date, order=frappe.qb.asc)
    )

    query = apply_filters(query, MpesaC2B, filters)
    records = query.run(as_dict=True)

    # Map docstatus to status label
    status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

    data = []
    current_customer = None
    subtotal = 0.0
    grand_total = 0.0

    for i, row in enumerate(records):
        row["status"] = status_map.get(row["docstatus"], "Unknown")

        if current_customer and current_customer != row["customer"]:
            # Add subtotal row for the previous customer
            data.append(
                {
                    "customer": f"Subtotal for {current_customer}",
                    "transamount": subtotal,
                    "status": "",
                }
            )
            data.append({})  # spacer row
            subtotal = 0.0

        current_customer = row["customer"]
        subtotal += row["transamount"]
        grand_total += row["transamount"]
        data.append(row)

        # On last record, close with the final customer's subtotal
        if i == len(records) - 1:
            data.append(
                {
                    "customer": f"Subtotal for {current_customer}",
                    "transamount": subtotal,
                    "status": "",
                }
            )

    # Append grand total row
    data.append({})
    data.append(
        {
            "customer": "Grand Total",
            "transamount": grand_total,
            "status": "",
        }
    )

    return data


def apply_filters(query, MpesaC2B, filters):
    if not filters:
        return query

    if filters.get("start_date"):
        query = query.where(MpesaC2B.posting_date >= filters["start_date"])

    if filters.get("end_date"):
        query = query.where(MpesaC2B.posting_date <= filters["end_date"])

    if filters.get("company"):
        query = query.where(MpesaC2B.company == filters["company"])

    if filters.get("status"):
        status_map = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
        docstatus = status_map.get(filters["status"])
        if docstatus is not None:
            query = query.where(MpesaC2B.docstatus == docstatus)

    return query
