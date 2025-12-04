// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mpesa Settings", {
	onload_post_render: function (frm) {
		frm.events.setup_account_balance_html(frm);
	},

	refresh: function (frm) {
		frappe.realtime.on("refresh_form", function () {
			frm.reload_doc();
		});
		frappe.realtime.on("refresh_mpesa_dashboard", function () {
			frm.reload_doc();
			frm.events.setup_account_balance_html(frm);
		});
	},
	get_account_balance: function (frm) {
		if (!frm.doc.initiator_name && !frm.doc.security_credential) {
			frappe.throw(__("Please set the initiator name and the security credential"));
		}
		frappe.call({
			method: "get_account_balance_info",
			doc: frm.doc,
		});
	},

	setup_account_balance_html: function (frm) {
		if (!frm.doc.account_balance) return;

		let text = frm.doc.account_balance;
		let rows = text.split("&");

		let data = {};

		rows.forEach((row) => {
			let parts = row.split("|");
			if (parts.length >= 6) {
				let [
					account_type,
					currency,
					current_balance,
					available_balance,
					reserved_balance,
					uncleared_balance,
				] = parts;

				data[account_type] = {
					currency,
					current_balance,
					available_balance,
					reserved_balance,
					uncleared_balance,
				};
			}
		});

		$("div").remove(".form-dashboard-section.custom");

		frm.dashboard.add_section(frappe.render_template("account_balance", { data: data }));

		frm.dashboard.show();
	},

	check_transaction_status: function (frm) {
		if (!frm.doc.initiator_name && !frm.doc.security_credential) {
			frappe.throw(__("Please set the initiator name and the security credential"));
		}
		frappe.clear_cache;
		frappe.prompt(
			[
				{
					label: "Transaction ID",
					fieldname: "transaction_id",
					fieldtype: "Data",
					reqd: 1,
				},
				{
					label: "Remarks",
					fieldname: "remarks",
					fieldtype: "Small Text",
				},
			],
			(values) => {
				frappe.call({
					method: "frappe_mpsa_payments.frappe_mpsa_payments.doctype.mpesa_settings.mpesa_settings.trigger_transaction_status",
					args: {
						mpesa_settings: frm.doc.name,
						transaction_id: values.transaction_id,
						remarks: values.remarks,
					},
					callback: (r) => {
						if (r.message && r.message.status === "queued") {
						} else {
							frappe.msgprint({
								message: __(r.message.message),
								title: r.message.status === "error" ? "Error" : "Success",
								indicator: r.message.status === "error" ? "red" : "green",
							});
						}
					},
					error: (err) => {
						frappe.msgprint({
							message: __("An error occurred: {0}", [err.message]),
							title: "Error",
							indicator: "red",
						});
					},
				});
			},
			__("Transaction Status Query"),
			__("Submit")
		);
	},
});
