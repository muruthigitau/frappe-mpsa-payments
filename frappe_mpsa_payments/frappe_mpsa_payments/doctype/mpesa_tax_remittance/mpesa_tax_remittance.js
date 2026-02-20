// Copyright (c) 2026, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mpesa Tax Remittance", {
	refresh(frm) {
		if (frm.doc.status !== "Completed" && frm.doc.docstatus == 1) {
			frm.add_custom_button(
				__("Initiate Tax Remittance"),
				function () {
					frappe.call({
						method: "initiate_request",
						doc: frm.doc,
						freeze: true,
						freeze_message: __("Initiating Tax Remittance..."),
						callback: function (r) {
							const res = r.message;
							if (res) {
								frappe.msgprint({
									message: res,
									indicator: "green",
									title: __("Tax Remittance Initiated"),
								});
							} else {
								frappe.msgprint(__("No response received."));
							}
						},
					});
				},
				__("Mpesa Actions"),
			);
		}
	},
});
