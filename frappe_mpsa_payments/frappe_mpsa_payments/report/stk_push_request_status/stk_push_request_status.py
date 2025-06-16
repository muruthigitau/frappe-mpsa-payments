# Copyright (c) 2025, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder import DocType


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    """Get the columns for the STK Push Request Status report.

    Returns:
        list: List of column definitions for the report.
    """
    return [
        {
            "fieldname": "timestamp",
            "fieldtype": "Datetime",
            "label": "Transaction Date",
            "width": 180,
        },
        {
            "fieldname": "transaction_id",
            "fieldtype": "Link",
            "label": "Request ID",
            "options": "Mpesa Express Request",
            "width": 150,
        },
        {
            "fieldname": "payment_request",
            "fieldtype": "Link",
            "label": "Payment Request",
            "options": "Payment Request",
            "width": 180,
        },
        {
            "fieldname": "voucher_type",
            "fieldtype": "Data",
            "label": "Voucher Type",
            "width": 150,
        },
        {
            "fieldname": "voucher_no",
            "fieldtype": "Link",
            "label": "Voucher No",
            "options": "Sales Invoice",
            "width": 150,
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


def get_data(filters):
    """Build and execute the Mpesa Express Request query."""
    MpesaExpressRequest = DocType("Mpesa Express Request")
    PaymentRequest = DocType("Payment Request")

    # TODO: Delete this commented code once the query is confirmed to work.
    # query = frappe.qb.from_(MpesaExpressRequest).select(
    #     MpesaExpressRequest.name.as_("transaction_id"),
    #     MpesaExpressRequest.amount,
    #     MpesaExpressRequest.phone_number,
    #     MpesaExpressRequest.status,
    #     MpesaExpressRequest.timestamp,
    #     MpesaExpressRequest.account_reference.as_("merchant_request_id"),
    #     MpesaExpressRequest.name.as_("checkout_request_id"),
    #     MpesaExpressRequest.checkout_request_id,
    #     MpesaExpressRequest.result_desc.as_("error_message"),
    # )

    query = (
        frappe.qb.from_(MpesaExpressRequest)
        .left_join(PaymentRequest)
        .on(MpesaExpressRequest.reference_name == PaymentRequest.name)
        .select(
            MpesaExpressRequest.name.as_("transaction_id"),
            MpesaExpressRequest.amount,
            MpesaExpressRequest.phone_number,
            MpesaExpressRequest.status,
            MpesaExpressRequest.timestamp,
            MpesaExpressRequest.account_reference.as_("merchant_request_id"),
            MpesaExpressRequest.name.as_("checkout_request_id"),
            MpesaExpressRequest.checkout_request_id,
            MpesaExpressRequest.result_desc.as_("error_message"),
            PaymentRequest.name.as_("payment_request"),
            PaymentRequest.reference_doctype.as_("voucher_type"),
            PaymentRequest.reference_name.as_("voucher_no"),
        )
    )

    query = apply_filters(query, filters)
    query = query.orderby(MpesaExpressRequest.timestamp, order=frappe.qb.desc)

    return query.run(as_dict=True)


def apply_filters(query, filters):
    MpesaExpressRequest = DocType("Mpesa Express Request")
    PaymentRequest = DocType("Payment Request")

    if filters.get("status"):
        query = query.where(MpesaExpressRequest.status == filters["status"])

    if filters.get("start_date"):
        query = query.where(
            MpesaExpressRequest.timestamp >= f"{filters['start_date']} 00:00:00"
        )

    if filters.get("end_date"):
        query = query.where(
            MpesaExpressRequest.timestamp <= f"{filters['end_date']} 23:59:59"
        )

    if filters.get("phone_number"):
        query = query.where(MpesaExpressRequest.phone_number == filters["phone_number"])

    if filters.get("voucher_type"):
        query = query.where(PaymentRequest.reference_doctype == filters["voucher_type"])

    if filters.get("voucher_no"):
        query = query.where(PaymentRequest.reference_name == filters["voucher_no"])

    return query
