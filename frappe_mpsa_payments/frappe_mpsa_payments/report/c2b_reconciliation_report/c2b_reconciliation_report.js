// Copyright (c) 2025, Navari Limited and contributors
// For license information, please see license.txt

frappe.query_reports['C2B Reconciliation Report'] = {
  filters: [
    {
      fieldname: 'posting_date',
      fieldtype: 'Date',
      label: __('Posting Date'),
      reqd: 1,
    },
    {
      fieldname: 'status',
      fieldtype: 'Select',
      label: __('Status'),
      options: ['', 'Draft', 'Submitted', 'Cancelled'],
      default: 'Submitted',
      reqd: 1,
    },
    {
      fieldname: 'unlinked_mpesa_payments',
      fieldtype: 'Check',
      label: __('Mpesa Payments not linked to a Payment Entry'),
    },
  ],
};
