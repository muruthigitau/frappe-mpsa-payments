frappe.listview_settings['Mpesa C2B Payment Register'] = {
    onload: function(listview) {
        // Add a custom button to the page actions (top bar)
        listview.page.add_inner_button(__("Check Transaction Status"), function() {
            frappe.prompt(
                [
                    {
                        label: "Mpesa Settings",
                        fieldname: "mpesa_settings",
                        fieldtype: "Link",
                        options: "Mpesa Settings",
                        reqd: 1
                    },
                    {
                        label: "Transaction ID",
                        fieldname: "transaction_id",
                        fieldtype: "Data",
                        reqd: 1
                    },
                    {
                        label: "Remarks",
                        fieldname: "remarks",
                        fieldtype: "Small Text"
                    }
                ],
                (values) => {
                    frappe.db.get_value("Mpesa Settings", values.mpesa_settings, ["initiator_name", "security_credential"], (settings) => {
                        if (!settings || (!settings.initiator_name && !settings.security_credential)) {
                            frappe.throw(__("Please set the initiator name and security credential in the selected Mpesa Settings"));
                        }

                        frappe.call({
                            method: "frappe_mpsa_payments.frappe_mpsa_payments.doctype.mpesa_settings.mpesa_settings.trigger_transaction_status",
                            args: {
                                mpesa_settings: values.mpesa_settings,
                                transaction_id: values.transaction_id,
                                remarks: values.remarks
                            },
                            callback: (r) => {
                                if (r.message && r.message.status === "queued") {
                                    // Wait for the transaction status to be processed
                                } else {
                                    frappe.msgprint({
                                        message: __(r.message.message),
                                        title: r.message.status === "error" ? "Error" : "Success",
                                        indicator: r.message.status === "error" ? "red" : "green"
                                    });
                                }
                            },
                            error: (err) => {
                                frappe.msgprint({
                                    message: __("An error occurred: {0}", [err.message]),
                                    title: "Error",
                                    indicator: "red"
                                });
                            }
                        });
                    });
                },
                __("Transaction Status Query"),
                __("Submit")
            );
        });
    },

    refresh: function(listview) {
        frappe.realtime.on("mpesa_transaction_status", function(data) {
            frappe.msgprint({
                message: __(data.message),
                title: data.status === "success" ? "Success" : "Error",
                indicator: data.status === "success" ? "green" : "red"
            });
            if (data.status === "success" && data.doc_name) {
                listview.refresh();
            }
        });
    }
};