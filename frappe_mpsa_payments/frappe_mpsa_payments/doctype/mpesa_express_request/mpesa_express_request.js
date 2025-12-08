// Copyright (c) 2025, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mpesa Express Request", {
	refresh(frm) {
		frappe.realtime.on("refresh_form", function () {
			frm.reload_doc();
		});

		autofill_gateway_settings(frm);

		if (frm.doc.status !== "Completed" && frm.doc.docstatus == 1) {
			frm.add_custom_button(
				__("Check Transaction Status"),
				function () {
					frappe.call({
						method: "frappe_mpsa_payments.frappe_mpsa_payments.api.m_pesa_api.check_transaction_status",
						args: {
							name: frm.doc.name,
						},
						freeze: true,
						freeze_message: __("Checking Transaction Status..."),
						callback: function (r) {
							if (r && r.message) {
								const res = r.message;

								if (res.ResultDesc && res.ResponseDescription) {
									const fullMessage = `
                  <b>Response:</b> ${res.ResponseDescription}<br>
                  <b>Result:</b> ${res.ResultDesc}
                `;

									const indicator = res.ResultCode === "0" ? "green" : "red";

									frappe.msgprint({
										message: fullMessage,
										indicator: indicator,
										title: __("Transaction Status"),
									});

									frm.reload_doc();
								} else if (res.errorMessage) {
									frappe.msgprint({
										message: res.errorMessage,
										indicator: "red",
										title: __("Error"),
									});
								} else {
									frappe.msgprint(
										__(
											"Missing ResultDesc or ResponseDescription in response."
										)
									);
								}
							} else {
								frappe.msgprint(__("No response received."));
							}
						},
					});
				},
				__("Mpesa Actions")
			);

			frm.add_custom_button(
				__("Initiate STK Push"),
				function () {
					frappe.call({
						method: "initiate_request",
						doc: frm.doc,
						freeze: true,
						freeze_message: __("Initiating STK Push..."),
						// args: {
						// 	document_name: frm.doc.name,
						// 	doctype: frm.doc.doctype,
						// 	payment_gateway: frm.doc.payment_gateway,
						// 	phone_number: frm.doc.phone_number,
						// 	request_amount: frm.doc.amount,
						// },
						callback: function (r) {
							const res = r.message;
							if (res) {
								frappe.msgprint({
									message: msg,
									indicator: "green",
									title: __("STK Push Initiated"),
								});
							} else {
								frappe.msgprint(__("No response received."));
							}
						},
					});
				},
				__("Mpesa Actions")
			);
		}

		if (!frm.doc.is_reconciled && frm.doc.status === "Completed" && frm.doc.docstatus == 1) {
			frm.add_custom_button(
				__("Reconcile Payment"),
				function () {
					frappe.call({
						method: "reconcile_payment",
						doc: frm.doc,
						freeze: true,
						freeze_message: __("Reconciling Payment..."),
						callback: function (r) {
							console.log(r);
						},
					});
				},
				__("Mpesa Actions")
			);
		}
	},

	settings: function (frm) {
		autofill_gateway_settings(frm);
	},
	payment_gateway: function (frm) {
		autofill_gateway_settings(frm);
	},
});

function autofill_gateway_settings(frm) {
	if (frm.doc.settings && !frm.doc.payment_gateway) {
		frappe.db
			.get_value("Payment Gateway", { gateway_controller: frm.doc.settings }, "name")
			.then((r) => {
				if (r.message) {
					frm.set_value("payment_gateway", r.message.name);
				}
			});
	} else if (frm.doc.payment_gateway && !frm.doc.settings) {
		frappe.db
			.get_value("Payment Gateway", { name: frm.doc.payment_gateway }, "gateway_controller")
			.then((r) => {
				if (r.message) {
					frm.set_value("settings", r.message.gateway_controller);
				}
			});
	}
}
