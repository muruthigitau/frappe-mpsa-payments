from typing import Literal

import frappe


def update_integration_request(
    integration_request: str,
    status: Literal["Completed", "Failed"],
    output: str | None = None,
    error: str | None = None,
) -> None:
    doc = frappe.get_doc("Integration Request", integration_request, for_update=True)
    doc.status = status
    doc.error = error
    doc.output = output
    doc.save(ignore_permissions=True)
