// Copyright (c) 2024, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mpesa Payment Reconciliation", {
	onload(frm) {
		if (frm.fields_dict.company) {
			const default_company = frappe.defaults.get_user_default("Company");
			frm.set_value("company", default_company);
		}
	},

	refresh(frm) {
		frm.disable_save();

		frm.set_df_property("invoices", "cannot_add_rows", true);
		frm.set_df_property("mpesa_payments", "cannot_add_rows", true);
		frm.set_df_property("invoices", "cannot_delete_rows", true);
		frm.set_df_property("mpesa_payments", "cannot_delete_rows", true);

		check_for_process_payments_button(frm);
	},

	customer(frm) {
		let fetch_btn = frm.add_custom_button(__("Get Unreconciled Entries"), () => {
			frm.trigger("fetch_entries");
		});
	},

	onload_post_render(frm) {
		frm.set_query("invoice_name", function () {
			return {
				filters: {
					docstatus: 1,
					outstanding_amount: [">", 0],
					company: frm.doc.company,
					customer: frm.doc.customer,
				},
			};
		});
	},

	refresh_reconciliation_entries(frm) {
		frm.clear_table("invoices");
		frm.clear_table("mpesa_payments");

		// Fetch outstanding invoices
		frappe.call({
			method: "frappe_mpsa_payments.frappe_mpsa_payments.api.payment_entry.get_outstanding_invoices",
			args: {
				company: frm.doc.company,
				currency: frm.doc.currency,
				customer: frm.doc.customer,
				voucher_no: frm.doc.invoice_name || "",
				from_date: frm.doc.from_invoice_date || "",
				to_date: frm.doc.to_invoice_date || "",
			},
			callback: function (response) {
				let draft_invoices = response.message;

				frm.clear_table("invoices");

				if (draft_invoices && draft_invoices.length > 0) {
					draft_invoices.forEach(function (invoice) {
						let row = frm.add_child("invoices");
						row.invoice = invoice.voucher_no;
						row.date = invoice.posting_date;
						row.total = invoice.invoice_amount;
						row.outstanding_amount = invoice.outstanding_amount;
					});
				}

				frm.refresh_field("invoices");
				check_for_process_payments_button(frm);
			},
		});

		// Fetch draft payments
		frappe.call({
			method: "frappe_mpsa_payments.frappe_mpsa_payments.api.m_pesa_api.get_mpesa_draft_c2b_payments",
			args: {
				company: frm.doc.company,
				full_name: frm.doc.full_name || "",
				from_date: frm.doc.from_mpesa_payment_date || "",
				to_date: frm.doc.to_mpesa_payment_date || "",
			},
			callback: function (response) {
				let draft_payments = response.message;

				frm.clear_table("mpesa_payments");

				if (draft_payments && draft_payments.length > 0) {
					draft_payments.forEach(function (payment) {
						let row = frm.add_child("mpesa_payments");
						row.payment_id = payment.name;
						row.full_name = payment.full_name;
						row.date = payment.posting_date;
						row.amount = payment.transamount;
					});
				}

				frm.refresh_field("mpesa_payments");
				check_for_process_payments_button(frm);

				if (frm.doc.invoices.length === 0 && frm.doc.mpesa_payments.length === 0) {
					frappe.msgprint({
						title: __("No Entries Found"),
						message: __(
							"No outstanding invoices or unreconciled payments found for the criteria."
						),
						indicator: "orange",
					});
				}
			},
		});
	},

	fetch_entries(frm) {
		frm.trigger("refresh_reconciliation_entries");
	},

	process_payments(frm, retryCount = 0) {
		let selected = frm.get_selected();

		let selected_invoices_rows = selected.invoices || [];
		let selected_payments_rows = selected.mpesa_payments || [];

		if (selected_invoices_rows.length === 0 || selected_payments_rows.length === 0) {
			frappe.msgprint({
				title: __("No Entries Selected"),
				message: __("Please select at least one invoice and one Mpesa payment."),
				indicator: "orange",
			});
			return;
		}

		let selected_invoices = frm.doc.invoices.filter((inv) =>
			selected_invoices_rows.includes(inv.name)
		);
		let selected_payments = frm.doc.mpesa_payments.filter((pay) =>
			selected_payments_rows.includes(pay.name)
		);

		let invoice_names = selected_invoices.map((i) => i.invoice);
		let mpesa_names = selected_payments.map((p) => p.payment_id);

		frappe.dom.freeze(__("Processing Mpesa Reconciliation…"));
		frm.custom_buttons && frm.custom_buttons["Allocate"]?.prop("disabled", true);

		return frappe.call({
			method: "frappe_mpsa_payments.frappe_mpsa_payments.api.payment_entry.process_mpesa_c2b_reconciliation",
			args: {
				invoice_names,
				mpesa_names,
			},
			callback: function (r) {
				if (r.exc) {
					frappe.show_alert(
						{
							message: __("Reconciliation failed. Check Error Log."),
							indicator: "red",
						},
						8
					);
				} else {
					frappe.show_alert(
						{
							message: __("Selected entries processed successfully"),
							indicator: "green",
						},
						5
					);
				}

				frm.trigger("refresh_reconciliation_entries");
			},
			always: function () {
				frappe.dom.unfreeze();
				frm.custom_buttons && frm.custom_buttons["Allocate"]?.prop("disabled", false);
			},
		});
	},
});

function check_for_process_payments_button(frm) {
	frm.remove_custom_button(__("Allocate"));

	if (
		frm.doc.invoices &&
		frm.doc.invoices.length > 0 &&
		frm.doc.mpesa_payments &&
		frm.doc.mpesa_payments.length > 0
	) {
		let process_btn = frm.add_custom_button(__("Allocate"), () => {
			frm.trigger("process_payments");
		});

		process_btn.addClass("btn-primary");
	}
}
