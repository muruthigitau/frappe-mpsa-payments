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
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
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
    PaymentEntry = DocType("Payment Entry")

    group_by_customer = filters.get("group_by_customer")

    # If not grouping, show flat list as before
    if not group_by_customer:
        query = (
            frappe.qb.from_(MpesaC2B)
            .select(
                MpesaC2B.customer,
                MpesaC2B.company,
                MpesaC2B.full_name.as_("customer_name"),
                MpesaC2B.transid,
                MpesaC2B.posting_date,
                MpesaC2B.transamount,
                MpesaC2B.docstatus,
            )
            .where(MpesaC2B.customer.isnotnull())
            .orderby(MpesaC2B.customer, order=frappe.qb.asc)
            .orderby(MpesaC2B.posting_date, order=frappe.qb.asc)
        )
        query = apply_filters(query, MpesaC2B, filters)
        records = query.run(as_dict=True)
        status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
        for row in records:
            row["status"] = status_map.get(row["docstatus"], "Unknown")
        return records

    # If grouping, fetch all customers with payments in the period
    customer_query = (
        frappe.qb.from_(MpesaC2B)
        .select(
            MpesaC2B.customer,
            MpesaC2B.company,
            MpesaC2B.full_name.as_("customer_name"),
        )
        .where(MpesaC2B.customer.isnotnull())
        .distinct()
    )
    customer_query = apply_filters(customer_query, MpesaC2B, filters)
    customers = customer_query.run(as_dict=True)

    status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
    data = []

    for customer in customers:
        # Parent row for customer (Group Header)
        data.append(
            {
                "customer": customer["customer"],
                "customer_name": customer["customer_name"],
                "is_group": 1,  # Mark as a group header
            }
        )

        # Fetch all C2B payments for this customer, joined with Payment Entry
        payment_query = (
            frappe.qb.from_(MpesaC2B)
            .left_join(PaymentEntry)
            .on(MpesaC2B.payment_entry == PaymentEntry.name)
            .select(
                MpesaC2B.transid,
                MpesaC2B.posting_date,
                MpesaC2B.transamount,
                MpesaC2B.docstatus,
                PaymentEntry.name.as_("payment_entry"),
                PaymentEntry.party,
                PaymentEntry.party_name,
                PaymentEntry.reference_no,
                PaymentEntry.reference_date,
                PaymentEntry.remarks,
            )
            .where(MpesaC2B.customer == customer["customer"])
            .orderby(
                MpesaC2B.posting_date, order=frappe.qb.asc
            )  # Order payments within customer group
        )
        payment_query = apply_filters(payment_query, MpesaC2B, filters)
        payments = payment_query.run(as_dict=True)

        customer_total_amount = 0.0

        for pay in payments:
            pay["status"] = status_map.get(pay["docstatus"], "Unknown")
            pay["is_group"] = 0  # Mark as a detail row
            data.append(pay)
            customer_total_amount += pay.get("transamount", 0.0)

        # Add the subtotal row after all payments for the current customer
        data.append(
            {
                "transamount": customer_total_amount,
                "is_subtotal": 1,  # Custom flag to identify subtotal rows
                "is_group": 1,  # Mark as group for visual grouping/styling if needed
                "transid": "SUBTOTAL",  # A placeholder for subtotal row
                "posting_date": None,
                "status": None,
                "company": None,  # Set other fields to None or empty for subtotal row
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
