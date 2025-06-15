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
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100,
        },
    ]


def get_data(filters):
    MpesaC2B = DocType("Mpesa C2B Payment Register")

    query = (
        frappe.qb.from_(MpesaC2B)
        .select(
            MpesaC2B.customer,
            Max(MpesaC2B.customer).as_("customer_name"),
            Sum(MpesaC2B.transamount).as_("total_amount"),
            Count(MpesaC2B.name).as_("payment_count"),
            Max(MpesaC2B.docstatus).as_("docstatus"),
        )
        .where(MpesaC2B.customer.isnotnull())
        .groupby(MpesaC2B.customer)
        .orderby(MpesaC2B.posting_date, order=frappe.qb.desc)
    )

    query = apply_filters(query, MpesaC2B, filters)

    data = query.run(as_dict=True)

    status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

    for row in data:
        row["status"] = status_map.get(row.get("docstatus"), "Unknown")

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
