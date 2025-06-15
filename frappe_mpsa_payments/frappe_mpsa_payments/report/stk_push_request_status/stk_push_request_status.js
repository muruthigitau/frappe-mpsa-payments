// Copyright (c) 2025, Navari Limited and contributors
// For license information, please see license.txt

frappe.query_reports["STK Push Request Status"] = {
	"filters": [
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nPending\nSuccess\nFailed",
			"default": "Pending",
		},
		{
			"fieldname": "start_date",
			"label": __("Start Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_days(frappe.datetime.get_today(), -30),
		}, 
		{
			"fieldname": "end_date",
			"label": __("End Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
		},
		{
			"fieldname": "phone_number",
			"label": __("Phone Number"),
			"fieldtype": "Data",
			"description": __("Filter by phone number (optional)"),
			"default": "",
		},
	]
};
