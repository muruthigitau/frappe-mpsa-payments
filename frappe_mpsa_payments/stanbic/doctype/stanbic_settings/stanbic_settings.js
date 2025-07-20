// Copyright (c) 2025, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("Stanbic Settings", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(
				__("Refresh Token"),
				() => {
					frm.call("refresh_access_token")
						.then((r) => {
							frm.refresh();
						})
						.catch(() => {});
				},
				"Actions"
			).addClass("btn-primary");

			frm.add_custom_button(
				__("Fetch All Sort Codes"),
				() => {
					frm.call("fetch_all_sort_codes").then(() => frm.reload_doc());
				},
				"Actions"
			);
		}
	},
});
