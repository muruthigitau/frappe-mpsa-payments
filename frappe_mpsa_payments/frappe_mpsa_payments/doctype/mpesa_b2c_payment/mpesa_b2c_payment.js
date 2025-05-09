// Copyright (c) 2024, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("MPesa B2C Payment", {
    onload: function (frm) {
      frm.set_query("mpesa_setting", function () {
        return {
          filters: {
            api_type: 'MPesa B2C (Business to Customer)',
          }
        };
      });
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

      if (has_failed_items && frm.doc.docstatus === 0) {
        frm.add_custom_button(__("Retry Failed Payments"), function() {
          frappe.confirm(
            'Retry failed payment entries?',
            function() {
              frappe.call({
                method: 'frappe_mpsa_payments.frappe_mpsa_payments.api.mpsa_b2c.retry_failed_payments',
                args: {
                  payment_name: frm.doc.name
                },
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
      frm.set_value("items", []);
      const doctype = frm.doc.doctype_to_pay_against;

      // Dynamic filters based on doctype
      const filterMap = {
        "Purchase Invoice": {
          outstanding_amount: [">", 0],
        },
        "Expense Claim": {
          approval_status: "Approved",
        },
        "Salary Slip": {
          status: "Submitted",
        }
      };

      // Apply common filters
      const filters = {
        ...filterMap[doctype],
        company: frm.doc.company,
        docstatus: 1,
        posting_date: ["between", [frm.doc.start_date, frm.doc.end_date]],
      };
  
      // Fetch relevant records and set relevant fields in items table
      frappe.db
        .get_list(doctype, {
          fields: ["*"],
          filters: filters,
        })
        .then((response) => {
          if (!response.length) {
            throw new Error("No Data Fetched");
          } else {
            if (doctype === "Employee Advance") {
              response = response.filter(data => {
                return (data.paid_amount || 0) < (data.advance_amount || 0);
              });
            }

            response.forEach(async (data) => {
              let recordData = {
                reference_doctype: doctype,
                record: data.name,
                receiver_name: data.employee ?? data.supplier,
                partyb: null,
                record_amount: (() => {
                  if (doctype === "Employee Advance") {
                    return (data.advance_amount || 0) - (data.paid_amount || 0);
                  }
                  return (
                    data.base_rounded_total ?? data.total_sanctioned_amount ?? data.advance_amount
                  );
                })(),
                  
              };
  
              // Apply fetching contact strategy according to document
              if (
                ["Salary Slip", "Expense Claim", "Employee Advance"].includes(doctype)
              ) {
                const contact = await frappe.db.get_value(
                  "Employee",
                  { name: data.employee ?? null },
                  ["cell_number"]
                );
  
                if (contact) {
                  recordData = {
                    ...recordData,
                    partyb: contact.message?.cell_number,
                  };
                }
              } else if (doctype === "Purchase Invoice") {
                const contact = await frappe.db.get_value(
                  "Contact",
                  { name: ["like", `%${data.supplier}%`] },
                  ["*"]
                );
  
                if (contact) {
                  recordData = {
                    ...recordData,
                    partyb: contact.message?.phone ?? contact.message?.mobile_no,
                  };
                }
              }
  
              // Update fields of child table with filtered data
              const row = frm.add_child("items");
              frappe.model.set_value(row.doctype, row.name, recordData);
              cur_frm.refresh_fields("items");
            });
          }
        })
        .catch((error) => {
          if (error.message === "No Data Fetched")
            frappe.msgprint({
              message: __(
                `No records fetched for doctype <b>${doctype}</b> with the <b>date filters specified</b>`
              ),
              indicator: "red",
              title: "No Data Fetched",
            });
        });
    },
    mpesa_setting: function (frm) {
      frappe.db.get_value(
        "Company",
        { name: frappe.boot.sysdefaults.company },
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
  