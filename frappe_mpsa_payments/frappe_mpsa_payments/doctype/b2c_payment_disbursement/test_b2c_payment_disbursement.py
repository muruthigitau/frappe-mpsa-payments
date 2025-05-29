# Copyright (c) 2024, Navari Limited and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from .b2c_payment_disbursement import B2CPaymentDisbursement
from unittest.mock import patch


class TestB2CPaymentDisbursement(FrappeTestCase):
    def setUp(self):
        self.payment_disbursement = B2CPaymentDisbursement()

    def test_uuid_generation(self):
        """Test that UUID is generated correctly."""
        self.payment_disbursement._generate_uuid_v4()
        self.assertTrue(self.payment_disbursement.uuid)
        self.assertEqual(len(self.payment_disbursement.uuid), 36)

    def test_validate_party_type(self):
        """Test that party type is validated correctly."""
        self.payment_disbursement.party_type = "Supplier"
        self.payment_disbursement.validate_party_type()
        self.assertEqual(self.payment_disbursement.party_type, "Customer")

        with self.assertRaises(frappe.ValidationError):
            self.payment_disbursement.party_type = "InvalidType"
            self.payment_disbursement.validate_party_type()

    def test_validate_mandatory_fields_missing_field(self):
        """Test that validate_mandatory_fields throws if a mandatory field is missing."""
        self.payment_disbursement.company = None
        self.payment_disbursement.posting_date = "2024-06-01"
        self.payment_disbursement.party_type = "Supplier"
        self.payment_disbursement.paid_from = "Test Paid From"
        self.payment_disbursement.paid_to = "Test Paid To"
        self.payment_disbursement.references = [frappe._dict()]
        self.payment_disbursement.meta = frappe._dict(get_label=lambda x: x)

        with self.assertRaises(frappe.ValidationError) as context:
            self.payment_disbursement.validate_mandatory_fields()

        self.assertIn("Field company is mandatory", str(context.exception))

    def test_validate_mandatory_fields_no_references(self):
        """Test that validate_mandatory_fields throws if references are missing."""
        self.payment_disbursement.company = "Test Company"
        self.payment_disbursement.posting_date = "2024-06-01"
        self.payment_disbursement.party_type = "Supplier"
        self.payment_disbursement.paid_from = "Test Paid From"
        self.payment_disbursement.paid_to = "Test Paid To"
        self.payment_disbursement.references = []
        self.payment_disbursement.meta = frappe._dict(get_label=lambda x: x)

        with self.assertRaises(frappe.ValidationError) as context:
            self.payment_disbursement.validate_mandatory_fields()

        self.assertIn("At least one reference is required", str(context.exception))

    def test_validate_mode_of_payment_required(self):
        """Test that validate_mode_of_payment throws if mode_of_payment is missing."""
        self.payment_disbursement.mode_of_payment = None

        with self.assertRaises(frappe.ValidationError) as context:
            self.payment_disbursement.validate_mode_of_payment()

        self.assertIn("Mode of Payment is required", str(context.exception))

    def test_validate_mode_of_payment_does_not_set_mpesa_setting_for_other_types(self):
        """Test that mpesa_setting is not set if payment_type is not Mpesa Disbursement."""
        self.payment_disbursement.mode_of_payment = "Mpesa-XYZ"
        self.payment_disbursement.payment_type = "Other Type"
        self.payment_disbursement.mpesa_setting = None

        # Patch frappe.db.get_value to raise if called
        original_get_value = frappe.db.get_value
        frappe.db.get_value = lambda *a, **k: (_ for _ in ()).throw(
            Exception("Should not be called")
        )
        try:
            self.payment_disbursement.validate_mode_of_payment()

            # Assert that mpesa_setting is still None
            self.assertIsNone(self.payment_disbursement.mpesa_setting)
        finally:
            frappe.db.get_value = original_get_value

    def test_validate_mode_of_payment_sets_mpesa_setting_for_mpesa_disbursement(self):
        """Test that mpesa_setting is set if payment_type is Mpesa Disbursement."""
        self.payment_disbursement.mode_of_payment = "Mpesa-XYZ"
        self.payment_disbursement.payment_type = "Mpesa Disbursement"
        self.payment_disbursement.mpesa_setting = None

        # Patch frappe.db.get_value to return a mock setting
        original_get_value = frappe.db.get_value
        frappe.db.get_value = lambda *a, **k: "Mock Mpesa Setting"
        try:
            self.payment_disbursement.validate_mode_of_payment()

            # Assert that mpesa_setting is set correctly
            self.assertEqual(
                self.payment_disbursement.mpesa_setting, "Mock Mpesa Setting"
            )
        finally:
            frappe.db.get_value = original_get_value

    def test_validate_party_type_employee(self):
        """Test that party_type 'Employee' passes validation."""
        self.payment_disbursement.party_type = "Employee"
        try:
            self.payment_disbursement.validate_party_type()
        except Exception as e:  # fail test if an exception is raised
            self.fail(
                "validate_party_type() raised Exception unexpectedly for 'Employee'"
                + str(e)
            )

    def test_validate_party_type_supplier(self):
        """Test that party_type 'Supplier' passes validation."""
        self.payment_disbursement.party_type = "Supplier"
        try:
            self.payment_disbursement.validate_party_type()
        except Exception as e:  # fail test if an exception is raised
            self.fail(
                "validate_party_type() raised Exception unexpectedly for 'Supplier' - "
                + str(e)
            )

    def test_validate_party_type_invalid(self):
        """Test that invalid party_type raises ValidationError."""
        self.payment_disbursement.party_type = "Customer"

        with self.assertRaises(frappe.ValidationError) as context:
            self.payment_disbursement.validate_party_type()

        self.assertIn("Party Type must be Employee or Supplier", str(context.exception))

    def test_validate_amounts_paid_amount_zero(self):
        """Test that validate_amounts throws if paid_amount is zero."""
        self.payment_disbursement.paid_amount = 0
        self.payment_disbursement.base_paid_amount = 100
        self.payment_disbursement.paid_from_account_currency = "KES"
        self.payment_disbursement.references = [frappe._dict(allocated_amount=0)]

        with self.assertRaises(frappe.ValidationError) as context:
            self.payment_disbursement.validate_amounts()
        self.assertIn("Paid Amount must be greater than zero", str(context.exception))

    def test_validate_amounts_paid_amount_negative(self):
        """Test that validate_amounts throws if paid_amount is negative."""
        self.payment_disbursement.paid_amount = -10
        self.payment_disbursement.base_paid_amount = 100
        self.payment_disbursement.paid_from_account_currency = "KES"
        self.payment_disbursement.references = [frappe._dict(allocated_amount=-10)]

        with self.assertRaises(frappe.ValidationError) as context:
            self.payment_disbursement.validate_amounts()
        self.assertIn("Paid Amount must be greater than zero", str(context.exception))

    def test_validate_amounts_base_paid_amount_required(self):
        """Test that validate_amounts throws if base_paid_amount is missing and currency is not KES."""
        self.payment_disbursement.paid_amount = 100
        self.payment_disbursement.base_paid_amount = None
        self.payment_disbursement.paid_from_account_currency = "USD"
        self.payment_disbursement.references = [frappe._dict(allocated_amount=100)]

        with self.assertRaises(frappe.ValidationError) as context:
            self.payment_disbursement.validate_amounts()
        self.assertIn(
            "Base Paid Amount (KES) is required for M-Pesa", str(context.exception)
        )

    def test_validate_amounts_total_allocated_not_equal_paid_amount(self):
        """Test that validate_amounts throws if total allocated does not equal paid_amount."""
        self.payment_disbursement.paid_amount = 100
        self.payment_disbursement.base_paid_amount = 100
        self.payment_disbursement.paid_from_account_currency = "KES"
        self.payment_disbursement.references = [
            frappe._dict(allocated_amount=60),
            frappe._dict(allocated_amount=30),
        ]

        with self.assertRaises(frappe.ValidationError) as context:
            self.payment_disbursement.validate_amounts()
        self.assertIn(
            "Total allocated amount 90.0 must equal Paid Amount 100",
            str(context.exception),
        )

    def test_validate_amounts_success(self):
        """Test that validate_amounts passes when all values are correct."""
        self.payment_disbursement.paid_amount = 150
        self.payment_disbursement.base_paid_amount = 150
        self.payment_disbursement.paid_from_account_currency = "KES"
        self.payment_disbursement.references = [
            frappe._dict(allocated_amount=50),
            frappe._dict(allocated_amount=100),
        ]
        try:
            self.payment_disbursement.validate_amounts()
        except Exception as e:  # fail test if an exception is raised
            self.fail(
                "validate_amounts() raised Exception unexpectedly when values are correct - "
                + str(e)
            )

    def test_validate_reference_doctypes_all_match(self):
        """Test that validate_reference_doctypes passes when all reference doctypes match."""
        self.payment_disbursement.transaction_to_pay_against = "Purchase Invoice"
        self.payment_disbursement.references = [
            frappe._dict(reference_doctype="Purchase Invoice", idx=1),
            frappe._dict(reference_doctype="Purchase Invoice", idx=2),
        ]

        try:
            self.payment_disbursement.validate_reference_doctypes()
        except Exception as e:
            self.fail(
                "validate_reference_doctypes() raised Exception unexpectedly when all doctypes match - "
                + str(e)
            )

    def test_validate_reference_doctypes_one_mismatch(self):
        """Test that validate_reference_doctypes throws if a reference doctype does not match."""
        self.payment_disbursement.transaction_to_pay_against = "Purchase Invoice"
        self.payment_disbursement.references = [
            frappe._dict(reference_doctype="Purchase Invoice", idx=1),
            frappe._dict(reference_doctype="Employee Advance", idx=2),
        ]

        with self.assertRaises(frappe.ValidationError) as context:
            self.payment_disbursement.validate_reference_doctypes()

        self.assertIn(
            "Reference doctype 'Employee Advance' does not match 'Purchase Invoice' for row 2",
            str(context.exception),
        )

    def test_validate_reference_doctypes_all_mismatch(self):
        """Test that validate_reference_doctypes throws for the first mismatch found."""
        self.payment_disbursement.transaction_to_pay_against = "Purchase Invoice"
        self.payment_disbursement.references = [
            frappe._dict(reference_doctype="Employee Advance", idx=1),
            frappe._dict(reference_doctype="Employee Advance", idx=2),
        ]

        with self.assertRaises(frappe.ValidationError) as context:
            self.payment_disbursement.validate_reference_doctypes()

        self.assertIn(
            "Reference doctype 'Employee Advance' does not match 'Purchase Invoice' for row 1",
            str(context.exception),
        )

    def test_set_missing_values_sets_company_currency(self):
        """Test that set_missing_values sets company_currency if missing."""

        self.payment_disbursement.company_currency = None
        self.payment_disbursement.paid_from_account_currency = "KES"
        self.payment_disbursement.posting_date = "2024-06-01"
        self.payment_disbursement.source_exchange_rate = 1.0
        self.payment_disbursement.paid_amount = 100
        
        # Patch frappe.get_cached_value
        original_get_cached_value = frappe.get_cached_value
        frappe.get_cached_value = lambda doctype, name, field: "KES"
        
        try:
            self.payment_disbursement.set_missing_values()
            self.assertEqual(self.payment_disbursement.company_currency, "KES")
        finally:
            frappe.get_cached_value = original_get_cached_value

    @patch("frappe.get_cached_value")
    def test_set_missing_values_does_not_set_company_currency_if_exists(self, mock_get_cached_value):
        """Test that set_missing_values does not overwrite company_currency if it already exists."""
        self.payment_disbursement.company_currency = "USD"
        self.payment_disbursement.paid_from_account_currency = "KES"
        self.payment_disbursement.posting_date = "2024-06-01"
        self.payment_disbursement.source_exchange_rate = 1.0
        self.payment_disbursement.paid_amount = 100
        
        # Mock get_cached_value to return a different currency
        mock_get_cached_value.return_value = "EUR"
        
        self.payment_disbursement.set_missing_values()
        
        # Assert that company_currency is still USD
        self.assertEqual(self.payment_disbursement.company_currency, "USD")

    @patch("frappe.get_cached_value")
    def test_set_missing_values_sets_source_exchange_rate(self, mock_get_cached_value):
        """Test that set_missing_values sets source_exchange_rate if missing."""
        self.payment_disbursement.source_exchange_rate = None
        self.payment_disbursement.paid_from_account_currency = "KES"
        self.payment_disbursement.company_currency = "USD"
        self.payment_disbursement.posting_date = "2024-06-01"
        self.payment_disbursement.paid_amount = 100
        
        # Mock get_cached_value to return a valid exchange rate
        mock_get_cached_value.return_value = 110.0
        
        self.payment_disbursement.set_missing_values()
        
        # Assert that source_exchange_rate is set correctly
        self.assertEqual(self.payment_disbursement.source_exchange_rate, 110.0)

    @patch("frappe.get_cached_value")
    def test_set_missing_values_does_not_set_source_exchange_rate_if_exists(self, mock_get_cached_value):
        """Test that set_missing_values does not overwrite source_exchange_rate if it already exists."""
        self.payment_disbursement.source_exchange_rate = 1.5
        self.payment_disbursement.paid_from_account_currency = "KES"
        self.payment_disbursement.company_currency = "USD"
        self.payment_disbursement.posting_date = "2024-06-01"
        self.payment_disbursement.paid_amount = 100
        
        # Mock get_cached_value to return a different exchange rate
        mock_get_cached_value.return_value = 2.0
        
        self.payment_disbursement.set_missing_values()
        
        # Assert that source_exchange_rate is still 1.5
        self.assertEqual(self.payment_disbursement.source_exchange_rate, 1.5)
