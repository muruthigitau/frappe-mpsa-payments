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
