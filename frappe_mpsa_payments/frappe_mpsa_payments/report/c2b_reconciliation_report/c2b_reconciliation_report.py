# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import DocType
from pypika.terms import Criterion


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
    MpesaC2B = DocType("Mpesa C2B Payment Register")

    query = (
        frappe.qb.from_(MpesaC2B)
        .select(
            MpesaC2B.posting_date,
            MpesaC2B.transactiontype,
            MpesaC2B.company,
            MpesaC2B.transid,
            MpesaC2B.transamount,
            MpesaC2B.payment_entry,
            MpesaC2B.docstatus,
        )
        .orderby(MpesaC2B.posting_date, order=frappe.qb.desc)
    )

    query = apply_filters(query, MpesaC2B, filters)

    data = query.run(as_dict=True)

    status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}

    for row in data:
        row["status"] = status_map.get(row["docstatus"], "Unknown")
        row["payment_entry"] = row.get("payment_entry", "No Payment Entry")

    return data


def apply_filters(query, MpesaC2B, filters):
    if not filters:
        return query

    if filters.get("posting_date"):
        query = query.where(MpesaC2B.posting_date >= filters["posting_date"])

    if filters.get("status"):
        status_map = {"Draft": 0, "Submitted": 1, "Cancelled": 2}
        docstatus = status_map.get(filters["status"])
        if docstatus is not None:
            query = query.where(MpesaC2B.docstatus == docstatus)

    if filters.get("unlinked_mpesa_payments"):
        query = query.where(
            (MpesaC2B.payment_entry.isnull()) | (MpesaC2B.payment_entry == "")
        )

    return query
