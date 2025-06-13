// Copyright (c) 2025, Navari Limited and contributors
// For license information, please see license.txt

frappe.query_reports['C2B Reconciliation Report'] = {
  filters: [
    {
      fieldname: 'start_date',
      fieldtype: 'Date',
      label: __('Start Date'),
      reqd: 1,
    },
    {
      fieldname: 'end_date',
      fieldtype: 'Date',
      label: __('End Date'),
      reqd: 1,
    },
    {
      fieldname: 'company',
      fieldtype: 'Link',
      label: __('Company'),
      options: 'Company',
      reqd: 0,
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
  formatter: function (value, row, column, data, default_formatter) {
    value = default_formatter(value, row, column, data);
    if (column.fieldname === 'status') {
      const colorMap = {
        Submitted: 'green',
        Cancelled: 'red',
        Draft: 'orange',
      };
      const color = colorMap[value];
      if (color) {
        value = `<span style="color: ${color}; font-weight: bold;">${value}</span>`;
      }
    }
    return value;
  },
};
