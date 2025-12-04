import frappe
from .patches.mpesa_custom_fields import create_custom_pos_fields
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


MODULE = "Frappe Mpsa Payments"


def is_app_installed(app_name: str) -> bool:
    return app_name in frappe.get_installed_apps()


def after_migrate():
    if is_app_installed("erpnext"):
        create_custom_pos_fields()
        create_custom_erpnext_fields()
        create_erpnext_property_setters()

    if is_app_installed("lending"):
        create_custom_lending_fields()

    if is_app_installed("hrms"):
        create_custom_hrms_fields()


def create_custom_lending_fields():
    custom_fields = {
        "Loan Disbursement": [
            {
                "fieldname": "b2c_payment_disbursement",
                "label": "B2C Payment Disbursement",
                "fieldtype": "Link",
                "insert_after": "reference_date",
                "options": "B2C Payment Disbursement",
                "read_only": 1,
            }
        ],
    }
    create_fields(custom_fields)


def create_custom_hrms_fields():
    custom_fields = {
        "B2C Payment Disbursement Reference": [
            {
                "depends_on": 'eval: doc.reference_doctype === "Salary Slip"',
                "fieldname": "payroll_entry",
                "fieldtype": "Link",
                "label": "Payroll Entry",
                "options": "Payroll Entry",
                "insert_after": "party",
            },
        ],
    }
    create_fields(custom_fields)


def create_custom_erpnext_fields():
    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "mpesa_payments",
                "label": "Fetch Mpesa Payments",
                "fieldtype": "Button",
                "insert_after": "payments_section",
            }
        ],
        "Sales Invoice Payment": [
            {
                "fieldname": "phone_number",
                "label": "Phone Number",
                "fieldtype": "Data",
                "insert_after": "amount",
                "read_only_depends_on": 'eval: doc.type !== "Phone"',
                "in_list_view": 1,
                "in_standard_filter": 1,
            },
            {
                "fieldname": "initiate_stk_push",
                "label": "Initiate STK Push",
                "fieldtype": "HTML",
                "insert_after": "clearance_date",
                "depends_on": 'eval: (doc.type == "Phone") && (!doc.reference_no)',
                "in_list_view": 1,
                "in_preview": 1,
                "in_standard_filter": 1,
            },
        ],
        "Bank": [
            {
                "fieldname": "pesa_link_bank_code",
                "label": "Pesa Link Bank Code",
                "fieldtype": "Data",
                "insert_after": "swift_number",
            }
        ],
        "Payment Entry Reference": [
            {
                "fieldname": "b2c_payment_disbursement",
                "label": "B2C Payment Disbursement",
                "fieldtype": "Link",
                "insert_after": "payment_request_outstanding",
                "options": "B2C Payment Disbursement",
            }
        ],
        "Journal Entry Account": [
            {
                "fieldname": "b2c_payment_disbursement",
                "label": "B2C Payment Disbursement",
                "fieldtype": "Link",
                "insert_after": "reference_detail_no",
                "options": "B2C Payment Disbursement",
            }
        ],
        "Sales Invoice": [
            {
                "fieldname": "initiate_stk_push",
                "label": "Initiate STK Push",
                "fieldtype": "Button",
                "insert_after": "base_paid_amount",
                "depends_on": "eval:doc.is_pos===1",
                "hidden": 1,
            }
        ],
        "Payment Request": [
            {
                "fieldname": "payment_token",
                "label": "Payment Token",
                "fieldtype": "Long Text",
                "insert_after": "column_break_iiuv",
                "hidden": 1,
            }
        ],
        "Mpesa Settings": [
            {
                "fieldname": "company",
                "label": "Company",
                "fieldtype": "Link",
                "options": "Company",
                "insert_after": "api_type",
            }
        ],
        "B2C Payment Disbursement": [
            {
                "fieldname": "company",
                "label": "Company",
                "fieldtype": "Link",
                "options": "Company",
                "insert_after": "posting_date",
                "reqd": 1,
            },
            {
                "fetch_from": "company.default_currency",
                "fieldname": "company_currency",
                "fieldtype": "Link",
                "hidden": 1,
                "label": "Company Currency",
                "options": "Currency",
                "read_only": 1,
                "insert_after": "company",
            },
            {
                "depends_on": "eval: doc.payment_type",
                "fieldname": "mode_of_payment",
                "fieldtype": "Link",
                "label": "Mode of Payment",
                "options": "Mode of Payment",
                "insert_after": "company_currency",
                "reqd": 1,
            },
            {
                "collapsible": 1,
                "fieldname": "accounts_section",
                "fieldtype": "Section Break",
                "label": "Accounts",
                "insert_after": "transaction_to_pay_against",
            },
            {
                "fieldname": "paid_from",
                "label": "Account Paid From",
                "fieldtype": "Link",
                "options": "Account",
                "insert_after": "accounts_section",
                "reqd": 1,
            },
            {
                "fieldname": "paid_from_account_type",
                "label": "Paid From Account Type",
                "fieldtype": "Data",
                "fetch_from": "paid_from.account_type",
                "hidden": 1,
                "insert_after": "paid_from",
            },
            {
                "fieldname": "paid_from_account_currency",
                "label": "Account Currency (From)",
                "fieldtype": "Link",
                "options": "Currency",
                "insert_after": "paid_from_account_type",
                "reqd": 1,
            },
            {
                "fieldname": "column_break_nsjt",
                "fieldtype": "Column Break",
                "insert_after": "paid_from_account_currency",
            },
            {
                "fieldname": "paid_to",
                "label": "Account Paid To",
                "fieldtype": "Link",
                "options": "Account",
                "insert_after": "column_break_nsjt",
                "reqd": 1,
            },
            {
                "fieldname": "paid_to_account_type",
                "label": "Paid To Account Type",
                "fieldtype": "Data",
                "fetch_from": "paid_to.account_type",
                "hidden": 1,
                "insert_after": "paid_to",
            },
            {
                "fieldname": "paid_to_account_currency",
                "label": "Account Currency (To)",
                "fieldtype": "Link",
                "options": "Currency",
                "read_only": 1,
                "reqd": 1,
                "insert_after": "paid_to_account_type",
            },
        ],
        "Mpesa C2B Payment Register": [
            {
                "fieldname": "company",
                "label": "Company",
                "fieldtype": "Link",
                "options": "Company",
                "insert_after": "posting_time",
            },
            {
                "fetch_from": "company.default_currency",
                "fieldname": "default_currency",
                "fieldtype": "Data",
                "label": "Default Currency",
                "read_only": 1,
                "insert_after": "company",
            },
            {
                "fieldname": "customer",
                "fieldtype": "Link",
                "in_list_view": 1,
                "in_preview": 1,
                "in_standard_filter": 1,
                "label": "Customer",
                "options": "Customer",
                "insert_after": "default_currency",
            },
            {
                "fieldname": "mode_of_payment",
                "fieldtype": "Link",
                "label": "Mode of Payment",
                "options": "Mode of Payment",
                "insert_after": "customer",
            },
            {
                "fieldname": "payment_entry",
                "fieldtype": "Link",
                "label": "Payment Entry",
                "options": "Payment Entry",
                "read_only": 1,
                "insert_after": "submit_payment",
            },
        ],
        "Mpesa C2B Payment Register URL": [
            {
                "fieldname": "company",
                "fieldtype": "Link",
                "in_list_view": 1,
                "in_standard_filter": 1,
                "label": "Company",
                "options": "Company",
                "reqd": 1,
                "insert_after": "column_break_4",
            },
            {
                "fieldname": "mode_of_payment",
                "fieldtype": "Link",
                "in_list_view": 1,
                "in_standard_filter": 1,
                "label": "Mode of Payment",
                "options": "Mode of Payment",
                "reqd": 1,
                "insert_after": "company",
            },
        ],
        "Mpesa Payment Reconciliation": [
            {
                "fieldname": "company",
                "fieldtype": "Link",
                "in_list_view": 1,
                "label": "Company",
                "options": "Company",
                "reqd": 1,
                "insert_after": "column_break_sbgx",
            },
            {
                "depends_on": "eval: doc.company",
                "fieldname": "customer",
                "fieldtype": "Link",
                "in_list_view": 1,
                "label": "Customer",
                "options": "Customer",
                "reqd": 1,
                "insert_after": "details_section",
            },
            {
                "fetch_from": "company.default_currency",
                "fieldname": "currency",
                "fieldtype": "Link",
                "label": "Currency",
                "options": "Currency",
                "read_only": 1,
                "insert_after": "customer",
            },
            {
                "fieldname": "invoice_name",
                "fieldtype": "Link",
                "label": "Invoice Name",
                "options": "Sales Invoice",
                "insert_after": "column_break_asbv",
            },
        ],
        "Stanbic Settings": [
            {
                "fieldname": "company",
                "fieldtype": "Link",
                "label": "Company",
                "options": "Company",
                "insert_after": "payment_gateway_name",
            },
        ],
        "Mpesa Payments Invoices": [
            {
                "fieldname": "invoice",
                "fieldtype": "Link",
                "in_list_view": 1,
                "in_preview": 1,
                "in_standard_filter": 1,
                "label": "Invoice",
                "options": "Sales Invoice",
                "read_only": 1,
                "insert_after": "details_section",
            },
        ],
    }
    create_fields(custom_fields)


def create_fields(custom_fields):
    for doctype, fields in custom_fields.items():
        for field in fields:
            field.setdefault("module", MODULE)

    create_custom_fields(custom_fields)


def create_erpnext_property_setters():
    property_setters = [
        {
            "doc_type": "Payment Request",
            "doctype_or_field": "DocType",
            "property": "field_order",
            "property_type": "Data",
            "value": (
                '["payment_request_type", "transaction_date", "phone_number", "column_break_2", '
                '"naming_series", "company", "mode_of_payment", "party_details", "party_type", '
                '"party", "party_name", "column_break_4", "reference_doctype", "reference_name", '
                '"transaction_details", "grand_total", "currency", "is_a_subscription", '
                '"column_break_18", "outstanding_amount", "party_account_currency", '
                '"subscription_section", "subscription_plans", "bank_account_details", '
                '"bank_account", "bank", "bank_account_no", "account", "column_break_11", "iban", '
                '"branch_code", "swift_number", "accounting_dimensions_section", "cost_center", '
                '"dimension_col_break", "project", "recipient_and_message", "print_format", '
                '"email_to", "subject", "column_break_9", "payment_gateway_account", "status", '
                '"make_sales_invoice", "section_break_10", "message", "message_examples", '
                '"mute_email", "payment_url", "section_break_7", "payment_gateway", '
                '"payment_account", "payment_channel", "payment_order", "amended_from", '
                '"column_break_iiuv", "payment_token"]'
            ),
        },
        {
            "doc_type": "Payment Request",
            "doctype_or_field": "DocField",
            "field_name": "phone_number",
            "property": "mandatory_depends_on",
            "property_type": "Data",
            "value": 'eval: doc.payment_channel == "Phone"',
        },
    ]
    for ps in property_setters:
        try:
            frappe.get_doc(
                {
                    "doctype": "Property Setter",
                    **ps,
                    "module": MODULE,
                }
            ).insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
