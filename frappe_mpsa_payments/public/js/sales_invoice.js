frappe.ui.form.on("Sales Invoice", {
  refresh(frm) {
    // Only show for POS invoices or drafts
    if (frm.doc.is_pos || frm.doc.docstatus === 0) {
      // Check if there's an outstanding amount > 0
      if (frm.doc.outstanding_amount > 0) {
        // Get company default currency
        frappe.call({
          method: "frappe.client.get_value",
          args: {
            doctype: "Company",
            filters: { name: frm.doc.company },
            fieldname: "default_currency",
          },
          callback: function (company_r) {
            // Get party account currency
            frappe.call({
              method: "frappe.client.get_value",
              args: {
                doctype: "Account",
                filters: { name: frm.doc.debit_to },
                fieldname: "account_currency",
              },
              callback: function (account_r) {
                const companyCurrency = company_r.message.default_currency;
                const partyAccountCurrency = account_r.message.account_currency;

                // Check if any currency is KES
                const isKES =
                  frm.doc.currency === "KES" ||
                  partyAccountCurrency === "KES" ||
                  companyCurrency === "KES";

                if (isKES) {
                  frappe.call({
                    method: "frappe.client.get_list",
                    args: {
                      doctype: "Mode of Payment",
                      filters: [["name", "like", "Mpesa%"]],
                      fields: ["name"],
                    },
                    callback: function (res) {
                      // Only show button if there's an Mpesa payment mode
                      if (res.message.length > 0) {
                        frm.add_custom_button(
                          __("Initiate STK Push"),
                          function () {
                            // Calculate amount once when button is clicked
                            let amount = frm.doc.outstanding_amount;

                            if (partyAccountCurrency !== "KES") {
                              if (frm.doc.conversion_rate) {
                                amount = amount * frm.doc.conversion_rate;
                              } else {
                                frappe.msgprint(
                                  __("Conversion rate not available")
                                );
                                return;
                              }
                            }
                            open_stk_push_dialog(frm, amount);
                          },
                          __("Mpesa Actions")
                        );
                      }
                    },
                  });
                }
              },
            });
          },
        });
      }
    }
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
        fieldname: "payment_gateway",
        label: "Payment Gateway",
        fieldtype: "Link",
        options: "Payment Gateway",
        reqd: 1,
        filters: {
          gateway_settings: "Mpesa Settings",
        },
      },
    ],
    primary_action_label: "Send STK Push",
    primary_action(values) {
      frappe.call({
        method:
          "frappe_mpsa_payments.frappe_mpsa_payments.api.m_pesa_api.initiate_invoice_stk_push",
        args: {
          invoice: frm.doc.name,
          phone_number: values.phone_number,
          amount: values.amount,
          payment_gateway: values.payment_gateway,
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
