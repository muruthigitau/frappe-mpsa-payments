// Copyright (c) 2025, Navari Limited and contributors
// For license information, please see license.txt

frappe.query_reports['B2C Disbursement Summary'] = {
  filters: [
    {
      fieldname: 'start_date',
      label: __('Start Date'),
      fieldtype: 'Date',
      default: frappe.datetime.add_months(frappe.datetime.get_today(), -5),
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
      required: 1,
      default: frappe.defaults.get_user_default('Company'),
    },
    {
      fieldname: 'party_type',
      label: __('Party Type'),
      fieldtype: 'Select',
      options: '\nEmployee\nSupplier\nCustomer',
    },
  ],
};
