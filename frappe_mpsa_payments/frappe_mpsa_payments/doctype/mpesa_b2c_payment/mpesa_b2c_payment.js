// Copyright (c) 2024, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("MPesa B2C Payment", {
    onload: function (frm) {
      frm.set_query("mpesa_setting", function () {
        
        if (!frm.doc.company) return false;

        return {
          filters: {
            api_type: 'MPesa B2C (Business to Customer)',
            company: frm.doc.company,
          }
        };
      });

      setTimeout(() => {
        const button_field = frm.fields_dict.fetch_entries;
        const $btn = button_field.$wrapper.find('.btn');
        $btn.removeClass('btn-xs').addClass('btn-sm btn-block text-left');
      }, 150)
    },
    
    refresh: function (frm) {
      // Set filters for party type field
      frm.set_query("party_type", function () {
        return {
          filters: [["DocType", "name", "in", ["Employee", "Supplier"]]],
        };
      });

      // Check if there are any failed entries
      let has_failed_items = frm.doc.items.some(item => item.payment_status === "Failed");

      if (has_failed_items && frm.doc.docstatus === 1) {
        frm.add_custom_button(__("Retry Failed Payments"), function() {
          frappe.confirm(
            'Retry failed payment entries?',
            function() {
              frappe.call({
                method: 'retry_failed_payments',
                doc: frm.doc,
                args: {},
                callback: function(r) {
                  if (r.message) {
                    frappe.msgprint(r.message);
                    frm.reload_doc();
                  }
                }
              });
            }
          );
        });
      }
    },
    commandid: function (frm) {
      frm.set_value("party_type", "");
  
      // Set appropriate party type according to commandid value
      if (frm.doc.commandid === "SalaryPayment") {
        frm.set_value("party_type", "Employee");
      } else if (frm.doc.commandid === "BusinessPayment") {
        frm.set_value("party_type", "Supplier");
      }
    },
    party_type: function (frm) {
      // Set filters to doctype to pay against field according to party type chosen
      frm.set_query("doctype_to_pay_against", function () {
        const doctypeFieldsList =
          frm.doc.party_type === "Employee"
            ? ["Salary Slip", "Expense Claim", "Employee Advance"]
            : ["Purchase Invoice", "Payment Entry"];
  
        return {
          filters: [["DocType", "name", "in", doctypeFieldsList]],
        };
      });

      // Set the start and end dates for the current month
      if (!frm.doc.start_date) {
        frm.set_value('start_date', frappe.datetime.month_start());
      }
      if (!frm.doc.end_date) {
        frm.set_value('end_date', frappe.datetime.month_end());
      }
    },
    doctype_to_pay_against: function (frm) {
      const doctype = frm.doc.doctype_to_pay_against;
      const company = frm.doc.company;
      
      const accountFieldMap = {
        "Employee Advance": "default_employee_advance_account",
        "Salary Slip": "default_payroll_payable_account"
      };

      const accountField = accountFieldMap[doctype];

      if (!accountField) return;
      
      frappe.db.get_value("Company", company, accountField)
        .then(response => {
          const account = response.message ? response.message[accountField] : null;
          if (account) {
            frm.set_value("account_paid_to", account);
          }
        })
    },

    fetch_entries(frm) {
      if (!frm.doc.party_type || !frm.doc.doctype_to_pay_against) {
        frappe.msgprint("Please select Party Type and Doctype to Pay Against");
        return;
      }

      frappe.call({
        method: "fetch_entries",
        doc: frm.doc,
        args: {
          docname: frm.doc.name,
          party_type: frm.doc.party_type,
          party: frm.doc.party || null,
          doctype_to_pay_against: frm.doc.doctype_to_pay_against,
          start_date: frm.doc.start_date,
          end_date: frm.doc.end_date,
        },
        callback: function(r) {
          if (r.message) {
            frm.clear_table("items");
            (r.message || []).forEach(row => {
              const child = frm.add_child("items", row);
            });
            frm.refresh_fields("items");
          }
        }
      });
    },

    mpesa_setting: function (frm) {
      frappe.db.get_value(
        "Company",
        { name: frm.doc.company },
        ["abbr"],
        (companyAbbrResponse) => {
          frappe.db.get_value(
            "Account",
            {
              name: [
                "like",
                `Mpesa-${frm.doc.mpesa_setting} - ${companyAbbrResponse.abbr}`,
              ],
            },
            ["name"],
            (response) => {
              frm.refresh_fields("account_paid_from");
              frm.set_value("account_paid_from", response.name);
            }
          );
        }
      );
    },
  });
  
  function generateUUIDv4() {
    // Generates a uuid4 string conforming to RFC standards
    let uuid = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      function (c) {
        let r = (Math.random() * 16) | 0,
          v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      }
    );
    return uuid;
  }
  
  function validatePhoneNumber(phoneNumber) {
    // Validates the receiver phone numbers
    if (phoneNumber.startsWith("2547")) {
      const pattern = /^2547\d{8}$/;
      return pattern.test(phoneNumber);
    } else {
      const pattern = /^(25410|25411)\d{7}$/;
      return pattern.test(phoneNumber);
    }
  }
  
  function sanitisePhoneNumber(phoneNumber) {
    phoneNumber = phoneNumber.replace("+", "").replace(/\s/g, "");
  
    const regex = /^0\d{9}$/;
    if (!regex.test(phoneNumber)) {
      return phoneNumber;
    }
  
    phoneNumber = "254" + phoneNumber.substring(1);
    return phoneNumber;
  }
  