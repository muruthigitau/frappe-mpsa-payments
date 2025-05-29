# Copyright (c) 2024, Navari Limited and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from .b2c_payment_disbursement import B2CPaymentDisbursement


class TestB2CPaymentDisbursement(FrappeTestCase):
    def setUp(self):
        self.payment_disbursement = B2CPaymentDisbursement()

    def test_uuid_generation(self):
        """Test that UUID is generated correctly."""
        self.payment_disbursement.generate_uuid()
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

        self.assertIn("At least one reference is required", str(context.exception))s

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
        frappe.db.get_value = lambda *a, **k: (_ for _ in ()).throw(Exception("Should not be called"))
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
            self.assertEqual(self.payment_disbursement.mpesa_setting, "Mock Mpesa Setting")
        finally:
            frappe.db.get_value = original_get_value
