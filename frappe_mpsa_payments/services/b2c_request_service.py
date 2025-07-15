import frappe
from frappe.utils import get_url

from frappe_mpsa_payments.connectors.factory import get_b2c_connector
from frappe_mpsa_payments.utils.doctype_names import B2C_REQUEST_DOCTYPE


def create_b2c_request(doc_name: str) -> dict:
    """
    Create and send a B2C Request.
    1) Loads the Disbursement Request.
    2) Picks the right connector via factory.
    3) Builds the callback URL.
    4) Dispatches the B2C payment request and returns the raw JSON.
    """
    doc = frappe.get_doc(B2C_REQUEST_DOCTYPE, doc_name)

    if doc.mpesa_settings:
        provider = "Mpesa"
        settings_name = doc.mpesa_settings
    elif doc.stanbic_settings:
        provider = "Stanbic"
        settings_name = doc.stanbic_settings
    else:
        frappe.throw(f"You must select either Mpesa or Stanbic settings on {doc_name}")

    callback_url = (
        f"{get_url()}/api/method/frappe_mpsa_payments.frappe_mpsa_payments.api.b2c.b2c_results_callback"
        f"?provider={provider}"
    )
    connector = get_b2c_connector(provider, settings_name)
    return connector.send_b2c_request(doc, callback_url)
