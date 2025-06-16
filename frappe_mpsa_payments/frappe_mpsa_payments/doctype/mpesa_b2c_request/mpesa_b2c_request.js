// Copyright (c) 2024, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mpesa B2C Request", {
	refresh(frm) {
        if (frm.doc.status === "Failed") {
            frm.add_custom_button("Retry Payment", () => {
                frappe.call({
                    method: "retry_failed_payment",
                    doc: frm.doc,
                    args: {},
                    callback: function(r) {
                        if (!r.exc) {
                            frm.reload_doc();
                        }
                    }
                });
            }, "Mpesa Actions");
        }
	},
});
