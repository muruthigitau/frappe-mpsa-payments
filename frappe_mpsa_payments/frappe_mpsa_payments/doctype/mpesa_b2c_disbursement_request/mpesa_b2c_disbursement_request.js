// Copyright (c) 2025, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mpesa B2C Disbursement Request", {
  refresh(frm) {
    if (frm.doc.docstatus === 1 && frm.doc.status !== "Completed") {
      frm.add_custom_button(
        __("Disburse"),
        () => {
          frappe.call({
            method:
              "frappe_mpsa_payments.frappe_mpsa_payments.api.m_pesa_api.disburse_b2c",
            args: { name: frm.doc.name },
            callback(r) {
              if (r.message) {
                frappe.msgprint(__("Disbursement initiated successfully."));
                frm.reload_doc();
              }
            },
          });
        },
        __("Actions")
      );
    }
  },
});
