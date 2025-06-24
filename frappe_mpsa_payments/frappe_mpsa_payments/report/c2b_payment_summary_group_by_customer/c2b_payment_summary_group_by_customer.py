# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import DocType
from pypika.terms import Criterion
from pypika.functions import Sum, Count, Max


def execute(filters=None):
    """
    Main function to execute the report.
    Fetches columns and data based on provided filters.
    """
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    """
    Defines and returns the column structure for the report.
    """
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
            "label": "Posting Date",
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Transaction ID",
            "fieldname": "transid",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Amount",
            "fieldname": "transamount",
            "fieldtype": "Currency",
            "width": 120,
        },
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
    ]


def get_docstatus_map():
    """
    Returns a mapping for docstatus integers to human-readable strings.
    """
    return {0: "Draft", 1: "Submitted", 2: "Cancelled"}


def _fetch_flat_payment_data(MpesaC2B, filters):
    """
    Fetches raw payment data from MpesaC2B for flat (non-grouped) display.
    """
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
    return query.run(as_dict=True)


def get_flat_data(MpesaC2B, filters):
    """
    Processes and formats data for flat (non-grouped) display.
    """
    records = _fetch_flat_payment_data(MpesaC2B, filters)
    status_map = get_docstatus_map()
    for row in records:
        row["status"] = status_map.get(row["docstatus"], "Unknown")
    return records


def get_distinct_customers(MpesaC2B, filters):
    """
    Fetches a distinct list of customers who have made payments based on filters.
    Includes company for the group header.
    """
    customer_query = (
        frappe.qb.from_(MpesaC2B)
        .select(
            MpesaC2B.customer,
            MpesaC2B.full_name.as_("customer_name"),
            MpesaC2B.company,
        )
        .where(MpesaC2B.customer.isnotnull())
        .distinct()
    )
    customer_query = apply_filters(customer_query, MpesaC2B, filters)
    return customer_query.run(as_dict=True)


def get_customer_payments(customer_id, MpesaC2B, PaymentEntry, filters):
    """
    Fetches all C2B payments for a given customer within the filter period,
    joined with Payment Entry details.
    """
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
        .where(MpesaC2B.customer == customer_id)
        .orderby(MpesaC2B.posting_date, order=frappe.qb.asc)
    )
    payment_query = apply_filters(payment_query, MpesaC2B, filters)
    return payment_query.run(as_dict=True)


def create_customer_group_header(customer):
    """
    Creates a dictionary representing a customer group header row for the report.
    """
    return {
        "customer": customer["customer"],
        "customer_name": customer["customer_name"],
        "company": customer["company"],
    }


def create_subtotal_row(customer_id, customer_name, total_amount):
    """
    Creates a dictionary representing a subtotal row for a customer.
    Includes fields necessary for proper display and grouping.
    """
    return {
        "transamount": total_amount,
        "transid": "SUBTOTAL",  # Placeholder for the Transaction ID column
    }


def get_data(filters):
    """
    Retrieves and processes payment data based on filters,
    optionally grouping by customer and adding subtotals.
    """
    MpesaC2B = DocType("Mpesa C2B Payment Register")
    PaymentEntry = DocType("Payment Entry")
    group_by_customer = filters.get("group_by_customer")

    if not group_by_customer:
        return get_flat_data(MpesaC2B, filters)

    customers = get_distinct_customers(MpesaC2B, filters)
    status_map = get_docstatus_map()
    data = []

    for customer in customers:
        data.append(create_customer_group_header(customer))

        payments = get_customer_payments(
            customer["customer"], MpesaC2B, PaymentEntry, filters
        )
        customer_total_amount = 0.0

        for pay in payments:
            pay["status"] = status_map.get(pay["docstatus"], "Unknown")
            data.append(pay)
            customer_total_amount += pay.get("transamount", 0.0)

        data.append(
            create_subtotal_row(
                customer["customer"], customer["customer_name"], customer_total_amount
            )
        )

    return data


def apply_filters(query, MpesaC2B, filters):
    """
    Applies common filters to the Frappe Query Builder query.
    """
    if not filters:
        return query

    if filters.get("start_date"):
        query = query.where(MpesaC2B.posting_date >= filters["start_date"])

    if filters.get("end_date"):
        query = query.where(MpesaC2B.posting_date <= filters["end_date"])

    if filters.get("company"):
        query = query.where(MpesaC2B.company == filters["company"])

    if filters.get("status"):
        status_map = get_docstatus_map()
        docstatus = status_map.get(filters["status"])
        if docstatus is not None:
            query = query.where(MpesaC2B.docstatus == docstatus)

    return query
