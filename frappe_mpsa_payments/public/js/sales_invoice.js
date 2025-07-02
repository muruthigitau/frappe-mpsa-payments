frappe.ui.form.on("Sales Invoice", {
  refresh(frm) {
    if (!frm.is_new() && frm.doc.is_pos && frm.doc.docstatus === 0) {
      if (frm.doc.outstanding_amount > 0) {
        frappe.call({
          method:
            "frappe_mpsa_payments.frappe_mpsa_payments.api.sales_invoice.validate_stk_push_eligibility",
          args: {
            docname: frm.doc.name,
            doctype: "Sales Invoice",
          },
          callback: function (response) {
            if (response.message && response.message.eligible) {
              frm.add_custom_button(
                __("Initiate STK Push"),
                function () {
                  open_stk_push_dialog(frm, response.message.amount);
                },
                __("Mpesa Actions")
              );
            }
          },
        });
      }
    }
    setup_stk_push_button_logic(frm);
  },

  onload_post_render: function (frm) {
    setup_stk_push_button_logic(frm);
  },

  payment: function (frm) {
    setup_stk_push_button_logic(frm);
  },

  mpesa_payments: function (frm) {
    frm.trigger("open_mpesa_payment_modal");
  },

  open_mpesa_payment_modal: function (frm) {
    // Fetch Mpesa payments
    frappe.call({
      method: "frappe.client.get_list",
      args: {
        doctype: "Mpesa C2B Payment Register",
        filters: {
          docstatus: 0,
        },
        fields: [
          "name",
          "transamount",
          "transid",
          "billrefnumber",
          "mode_of_payment",
          "full_name",
          "posting_date",
        ],
      },
      callback: function (response) {
        const payments = response.message;
        if (payments.length) {
          // Create the modal
          let dialog = new frappe.ui.Dialog({
            title: __("Select Mpesa Payment"),
            fields: [
              {
                fieldname: "mpesa_payment",
                label: "Mpesa Payment",
                fieldtype: "Table",
                cannot_add_rows: true,
                data: payments,
                fields: [
                  {
                    fieldname: "name",
                    label: __("Name"),
                    fieldtype: "Link",
                    options: "Mpesa C2B Payment Register",
                    in_list_view: 0,
                    read_only: 1,
                  },
                  {
                    fieldname: "posting_date",
                    label: __("Posting Date"),
                    fieldtype: "Date",
                    in_list_view: 1,
                    read_only: 1,
                  },
                  {
                    fieldname: "mode_of_payment",
                    label: __("Mode of Payment"),
                    fieldtype: "Link",
                    options: "Mode of Payment",
                    in_list_view: 0,
                    read_only: 1,
                  },
                  {
                    fieldname: "full_name",
                    label: __("Full Name"),
                    fieldtype: "Data",
                    in_list_view: 1,
                    read_only: 1,
                  },
                  {
                    fieldname: "transid",
                    label: __("Transaction ID"),
                    fieldtype: "Data",
                    in_list_view: 1,
                    read_only: 1,
                  },
                  {
                    fieldname: "transamount",
                    label: __("Payment Amount"),
                    fieldtype: "Currency",
                    in_list_view: 1,
                    read_only: 1,
                  },
                ],
              },
            ],
            primary_action_label: "Add Payment",
            primary_action: function (data) {
              if (data.mpesa_payment && data.mpesa_payment.length > 0) {
                const customer = frm.doc.customer;
                // Loop through selected payments and add them to the Sales Invoice
                data.mpesa_payment.forEach((payment) => {
                  // Update the payment with the customer
                  frappe.call({
                    method: "frappe.client.get",
                    args: {
                      doctype: "Mpesa C2B Payment Register",
                      name: payment.name,
                    },
                    callback: function (paymentDocResponse) {
                      let paymentDoc = paymentDocResponse.message;

                      paymentDoc.customer = customer;

                      frm.clear_table("payments");

                      frm.add_child("payments", {
                        mode_of_payment: payment.mode_of_payment,
                        amount: payment.transamount,
                        reference_no: payment.transid,
                      });
                      frm.refresh_field("payments");
                      dialog.hide();
                    },
                  });
                });
              } else {
                frappe.msgprint(__("Please select a payment."));
              }
            },
          });
          dialog.show();
        } else {
          frappe.msgprint(__("No draft Mpesa payments available."));
        }
      },
    });
  },

  insert_payment_entry: function (frm) {
    frappe.call({
      method: "frappe.client.insert",
      args: {
        doc: {
          doctype: "Payment Entry",
          payment_type: "Receive",
          party_type: "Customer",
          party: frm.doc.customer,
          paid_to: "Cash",
          reference_no: payment_response["MpesaReceiptNumber"],
          amount: frm.doc.grand_total,
        },
      },
    });
  },
});

frappe.ui.form.on("Sales Invoice Payment", {
  type: function (frm, cdt, cdn) {
    setup_stk_push_button_logic(frm);
  },
  reference_no: function (frm, cdt, cdn) {
    setup_stk_push_button_logic(frm);
  },
  payment_type: function (frm, cdt, cdn) {
    setup_stk_push_button_logic(frm);
  },
  payment_gateway: function (frm, cdt, cdn) {
    setup_stk_push_button_logic(frm);
  },
  mode_of_payment: function (frm, cdt, cdn) {
    setup_stk_push_button_logic(frm);
  },
});

function setup_stk_push_button_logic(frm) {
  if (frm.is_new()) {
    return;
  }
  const child_table = frm.doc.payments || [];

  child_table.forEach((row) => {
    const cdt = "Sales Invoice Payment";
    const cdn = row.name;

    if (row.type === "Phone" && !row.reference_no) {
      frappe.model.set_value(
        cdt,
        cdn,
        "initiate_stk_push",
        `
        <div style="margin-top:5px;">
          <button class="btn btn-primary btn-xs stk-button" data-row-name="${cdn}">
            Initiate STK Push
          </button>
        </div>
      `
      );
    } else {
      frappe.model.set_value(cdt, cdn, "initiate_stk_push", "");
    }
  });

  setTimeout(() => {
    frm.fields_dict.payments.grid.grid_rows.forEach((grid_row) => {
      const $btn = $(grid_row.wrapper).find(".stk-button");

      $btn.off("click").on("click", function () {
        const row_name = $(this).data("row-name");
        const row = frm.doc.payments.find((r) => r.name === row_name);

        if (row) {
          initiate_stk_push_child(frm, row);
        }
      });
    });
  }, 300);
}

function initiate_stk_push_child(frm, row) {
  if (row.type !== "Phone") {
    frappe.msgprint(__("STK Push is only allowed for Phone type payments."));
    return;
  }

  if (!row.phone_number) {
    frappe.msgprint(__("Please enter a phone number to initiate STK Push."));
    return;
  }

  frappe.call({
    method:
      "frappe_mpsa_payments.frappe_mpsa_payments.api.sales_invoice.get_stk_amount",
    args: {
      payment_name: row.name,
      company: frm.doc.company,
    },
    callback(amount_res) {
      const final_amount = amount_res.message;

      if (!final_amount) {
        frappe.msgprint(
          __(
            "STK Push is only supported for KES payments or if company's default currency is KES."
          )
        );
        return;
      }

      frappe.call({
        method:
          "frappe_mpsa_payments.frappe_mpsa_payments.api.sales_invoice.initiate_row_stk_push",
        args: {
          name: row.name,
          phone_number: row.phone_number,
          amount: final_amount,
          mode_of_payment: row.mode_of_payment,
          company: frm.doc.company,
        },
        callback(r) {
          if (!r.exc) {
            frappe.msgprint(__("STK Push initiated successfully."));
            frm.refresh();

            setup_stk_push_button_logic(frm);
          }
        },
      });
    },
  });
}

function open_stk_push_dialog(frm, amount) {
  const dialog = new frappe.ui.Dialog({
    title: __("Initiate STK Push"),
    fields: [
      {
        fieldname: "phone_number",
        label: "Phone Number",
        fieldtype: "Data",
        reqd: 1,
        options: "Phone",
      },
      {
        fieldname: "amount",
        label: "Amount (KES)",
        fieldtype: "Currency",
        default: amount,
        reqd: 1,
      },
      {
        fieldname: "mode_of_payment",
        label: "Mode of Payment",
        fieldtype: "Link",
        options: "Mode of Payment",
        get_query: function () {
          return {
            filters: {
              type: "Phone",
            },
          };
        },
        reqd: 1,
      },
    ],
    primary_action_label: "Send STK Push",
    primary_action(values) {
      frappe.call({
        method:
          "frappe_mpsa_payments.frappe_mpsa_payments.api.sales_invoice.initiate_invoice_stk_push",
        args: {
          invoice: frm.doc.name,
          phone_number: values.phone_number,
          amount: values.amount,
          mode_of_payment: values.mode_of_payment,
          company: frm.doc.company,
          type: "Sales Invoice",
        },
        callback(r) {
          if (!r.exc) {
            frappe.msgprint(__("STK Push initiated successfully."));
            dialog.hide();
            frm.refresh();
          }
        },
      });
    },
  });

  dialog.show();
}
