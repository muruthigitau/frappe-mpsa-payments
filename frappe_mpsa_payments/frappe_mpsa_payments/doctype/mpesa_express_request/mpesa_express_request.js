// Copyright (c) 2025, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mpesa Express Request", {
  refresh(frm) {
    frappe.realtime.on("refresh_form", function () {
      frm.reload_doc();
    });

    frm.add_custom_button(
      __("Check Transaction Status"),
      function () {
        frappe.call({
          method:
            "frappe_mpsa_payments.frappe_mpsa_payments.api.m_pesa_api.check_transaction_status",
          args: {
            name: frm.doc.name,
          },
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
                  __("Missing ResultDesc or ResponseDescription in response.")
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
          method:
            "frappe_mpsa_payments.frappe_mpsa_payments.api.m_pesa_api.initiate_stk_push",
          args: {
            document_name: frm.doc.name,
            doctype: frm.doc.doctype,
            payment_gateway: frm.doc.payment_gateway,
            phone_number: frm.doc.phone_number,
            request_amount: frm.doc.amount,
          },
          callback: function (r) {
            const res = r.message;
            if (res) {
              if (res.errorMessage) {
                frappe.msgprint({
                  message: res.errorMessage,
                  indicator: "red",
                  title: __("Error"),
                });
              } else if (res.CustomerMessage || res.message?.CustomerMessage) {
                const msg = res.CustomerMessage || res.message.CustomerMessage;
                frappe.msgprint({
                  message: msg,
                  indicator: "green",
                  title: __("STK Push Initiated"),
                });
              } else {
                frappe.msgprint(__("Unexpected response."));
              }

              frm.reload_doc();
            } else {
              frappe.msgprint(__("No response received."));
            }
          },
        });
      },
      __("Mpesa Actions")
    );
  },
});
