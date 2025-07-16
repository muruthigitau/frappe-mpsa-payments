from __future__ import annotations

import json
from enum import Enum

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime, nowdate

from ...utils.doctype_names import B2C_REQUEST_DOCTYPE, STANBIC_SETTINGS_DOCTYPE
from ..abstract import B2CConnector
from ..base_connector import (
    BaseAPIConnector,
    create_request_log,
    update_integration_request,
)


class Baseurl(Enum):
    SANDBOX_URL = "https://api.connect.stanbicbank.co.ke/api/sandbox"
    LIVE_URL = "https://api.connect.stanbicbank.co.ke/api/sandbox"


class StanbicConnector(BaseAPIConnector, B2CConnector):
    """
    Connector for Stanbic Bank PesaLink and Mobile Money APIs.
    Handles OAuth2 token retrieval, caching, and executing requests
    with full audit logging and error handling.
    """

    provider_name = "Stanbic"

    def __init__(self, settings_name):
        """
        Initialize the StanbicConnector.

        Args:
            settings_name: The name of the Stanbic Settings document.
        """
        super().__init__(
            provider="Stanbic",
            settings_doctype=STANBIC_SETTINGS_DOCTYPE,
            settings_name=settings_name,
        )
        self._load_settings()

    def _load_settings(self):
        """
        Load Stanbic Settings into instance attributes.

        Expects the Stanbic Settings DocType to have fields:
        - client_id
        - client_secret (password)
        - access_token
        - scope
        - token_expiry
        """
        s = frappe.get_doc(
            STANBIC_SETTINGS_DOCTYPE, self.settings_name, ignore_permissions=True
        )
        self.client_id = s.client_id
        self.client_secret = s.get_password("client_secret")
        self._token = s.access_token
        self.scope = s.scope or "payments"
        self.mobile_number = s.mobile_number
        self._token_expiry = s.token_expiry
        self._base_url = (
            Baseurl.SANDBOX_URL.value if s.sandbox else Baseurl.LIVE_URL.value
        )

    def _is_token_valid(self) -> bool:
        """
        Check if a cached access token exists and is unexpired.

        Returns:
            True if a valid token is cached, False otherwise.
        """
        return (
            self._token and self._token_expiry and now_datetime() < self._token_expiry
        )

    def _refresh_token(self, manual_refresh=False) -> str:
        """
        Retrieve or refresh the OAuth2 token from Stanbic.

        If the existing token is valid, returns it; otherwise, makes
        a POST to the token_url with form-encoded credentials and scope.

        Returns:
            A valid access token string.
        """

        if self._is_token_valid() and not manual_refresh:
            return self._token

        form = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scope,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        data = (
            self.describe("Stanbic OAuth2 Token")
            .set_endpoint("/auth/oauth2/token")
            .set_method("POST")
            .set_headers(headers)
            .set_payload(form)
            .use_form_data(True)
            .make_remote_call(self._base_url, self.settings_doctype, self.settings_name)
        )

        token = data["access_token"]
        scope = data["scope"]
        expires_in = int(data.get("expires_in", 0))
        expiry = add_to_date(now_datetime(), seconds=expires_in)

        frappe.db.set_value(
            STANBIC_SETTINGS_DOCTYPE,
            self.settings_name,
            {"access_token": token, "scope": scope, "token_expiry": expiry},
        )
        frappe.db.commit()

        self._token = token
        self._token_expiry = expiry
        return token

    def _get_valid_token(self) -> str:
        if not self._is_token_valid():
            self._refresh_token()
        return self._token

    def send_b2c_request(self, request_doc: Document, callback_url: str) -> dict:
        """
        Dispatch a B2C payment request via Stanbic:
        • If request_doc.phone_number exists → Mobile-Money
        • Else if request_doc.bank_ac_no exists → PesaLink
        """
        token = self._get_valid_token()

        self.on_success(self._handle_success).on_error(self._handle_error)

        # base payload common parts
        today = nowdate()
        base_payload = {
            "originatorAccount": {
                "identification": {"mobileNumber": self.mobile_number}
            },
            "requestedExecutionDate": today,
            "dbsReferenceId": request_doc.dbs_reference_id,
            "txnNarrative": request_doc.remarks,
            "callBackUrl": callback_url,
            "transferTransactionInformation": {
                "instructedAmount": {
                    "amount": f"{request_doc.amount:.2f}",
                    "currencyCode": request_doc.currency,
                },
                "remittanceInformation": {
                    "type": "UNSTRUCTURED",
                    "content": request_doc.remarks,
                },
                "endToEndIdentification": request_doc.originator_conversation_id,
            },
        }

        # Decide which API to call
        if request_doc.get("phone_number"):
            endpoint = "/mobile-payments"

            base_payload["transferTransactionInformation"].update(
                {
                    "mobileMoneyMno": {
                        "name": "MPESA"  # TODO: need a better approach for this options: MPESA or AIRTEL MONEY or T-KASH
                    },
                    "counterparty": {
                        "name": request_doc.party,
                        "mobileNumber": request_doc.phone_number,
                        "postalAddress": {
                            "addressLine1": "",
                            "addressLine2": "",
                            "postCode": "",
                            "town": "",
                            "country": "",
                        },
                    },
                }
            )

        elif request_doc.get("bank_ac_no"):
            endpoint = "/pesalink-payments"

            base_payload.update({"sendMoneyTo": "ACCOUNT.NUMBER"})
            base_payload["transferTransactionInformation"].update(
                {
                    "counterpartyAccount": {
                        "identification": {
                            "recipientBankAcctNo": request_doc.bank_ac_no,
                            "recipientBankCode": request_doc.bank_code,
                        }
                    },
                    "counterparty": {
                        "name": request_doc.party,
                        "postalAddress": {
                            "addressLine": "",
                            "postCode": "",
                            "town": "",
                            "country": "",
                        },
                    },
                }
            )

        else:
            frappe.throw(
                "Neither phone_number nor bank_ac_no is set on this B2C request"
            )

        return (
            self.describe("Stanbic B2C")
            .set_endpoint(endpoint)
            .set_method("POST")
            .set_headers(
                {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
            .set_payload(base_payload)
            .make_remote_call(
                self._base_url,
                doctype=request_doc.doctype,
                document_name=request_doc.name,
            )
        )

    def _handle_success(
        self,
        response=None,
        data=None,
        doctype=None,
        document_name=None,
        integration_request=None,
        settings_name=None,
        **kwargs,
    ):
        try:
            status = "Paid" if data.get("bankStatus") == "ACCEPTED" else "Failed"

            fields = {
                "transaction_id": data.get("bankReferenceId"),
                "status": status,
                "response_code": data.get("reasonCode", ""),
                "response_description": data.get("reasonText", ""),
                "next_execution_date": data.get("nextExecutionDate"),
            }

            for key, val in fields.items():
                frappe.db.set_value(B2C_REQUEST_DOCTYPE, document_name, key, val)
            frappe.log(f"Stanbic B2C Request updated for {document_name}")

            update_integration_request(
                integration_request.name,
                status="Completed",
                output=json.dumps(data),
            )
            frappe.db.commit()

            frappe.publish_realtime(
                event="refresh_form", doctype=B2C_REQUEST_DOCTYPE, docname=document_name
            )

        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"Stanbic B2C Success Error for {document_name}"
            )
            raise

    def _handle_error(
        self,
        response=None,
        data=None,
        error=None,
        doctype=None,
        document_name=None,
        integration_request=None,
        settings_name=None,
        **kwargs,
    ):
        if error is not None:
            frappe.log_error(frappe.get_traceback(), "Stanbic B2C Transport Error")
            update_integration_request(
                integration_request.name,
                status="Failed",
                output=str(error),
            )
            frappe.db.commit()
            return

        fields = {
            "status": "Failed",
            "error_code": data.get("httpCode", ""),
            "request_id": data.get("httpMessage"),
            "error_message": data.get("moreInformation", ""),
        }
        for key, val in fields.items():
            frappe.db.set_value(B2C_REQUEST_DOCTYPE, document_name, key, val)

        update_integration_request(
            integration_request.name,
            status="Failed",
            output=json.dumps(data),
        )
        frappe.db.commit()

        frappe.publish_realtime(
            event="refresh_form", doctype=B2C_REQUEST_DOCTYPE, docname=document_name
        )

    def handle_callback(self, payload: dict) -> None:
        """
        Called when Stanbic posts to your ResultURL.
        We:
        1) Log the callback as its own Integration Request
        2) Update the B2C Request record
        3) Update that callback‐log
        4) Enqueue reference‐status + postprocess
        """

        dbs_ref = payload.get("dbsReferenceId")
        req = frappe.get_doc(
            B2C_REQUEST_DOCTYPE, {"dbs_reference_id": dbs_ref}, ignore_permissions=True
        )

        self.integration_request = create_request_log(
            data=payload,
            request_description="Stanbic B2C Callback",
            is_remote_request=True,
            service_name=self.provider,
            request_headers={},
            url=f"{self._base_url}/pesalink-payments/callback",
            reference_doctype=req.doctype,
            reference_docname=req.name,
        )

        update_map = {
            "status": "Paid" if payload.get("bankStatus") == "ACCEPTED" else "Failed",
            "transaction_id": payload.get("bankReferenceId"),
            "response_code": payload.get("reasonCode", ""),
            "response_description": payload.get("reasonText", ""),
            "next_execution_date": payload.get("nextExecutionDate"),
        }
        for k, v in update_map.items():
            if v is not None:
                setattr(req, k, v)
        req.save(ignore_permissions=True)

        update_integration_request(
            self.integration_request.name,
            status=req.status,
            output=json.dumps(payload),
        )
        frappe.db.commit()

        frappe.enqueue(
            "frappe_mpsa_payments.services.b2c_response_service.update_b2c_reference_status",
            queue="short",
            timeout=300,
            b2c_request_name=req.name,
            enqueue_next=True,
        )
