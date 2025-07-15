import frappe


def update_b2c_disbursement_statuses():
    """
    Scheduler job to retry outstanding disbursements (retry_count ≤ 3)
    """
    disbs = frappe.get_all(
        "B2C Payment Disbursement",
        filters={
            "docstatus": 1,
            "retry_count": ["<=", 3],
            "status": ["not in", ["Paid", "Not Initiated"]],
        },
        fields=["name"],
    )
    for d in disbs:
        try:
            doc = frappe.get_doc("B2C Payment Disbursement", d.name)
            result = doc.update_disbursement_status()
            frappe.log(f"[B2C Retry] {d.name}: {result}")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"[B2C Retry Error] {d.name}")
