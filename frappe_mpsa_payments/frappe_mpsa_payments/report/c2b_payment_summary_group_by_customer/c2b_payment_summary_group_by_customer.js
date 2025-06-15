// Copyright (c) 2025, Navari Limited and contributors
// For license information, please see license.txt

frappe.query_reports['C2B Payment Summary Group by Customer'] = {
  filters: [
    {
      fieldname: 'start_date',
      label: __('Start Date'),
      fieldtype: 'Date',
      default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
      reqd: 1,
    },
    {
      fieldname: 'end_date',
      label: __('End Date'),
      fieldtype: 'Date',
      default: frappe.datetime.get_today(),
      reqd: 1,
    },
    {
      fieldname: 'company',
      label: __('Company'),
      fieldtype: 'Link',
      options: 'Company',
    },
    {
      fieldname: 'status',
      label: __('Status'),
      fieldtype: 'Select',
      options: '\nDraft\nSubmitted\nCancelled',
    },
  ],
};
