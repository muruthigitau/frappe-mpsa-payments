from __future__ import annotations

from enum import Enum
from typing import Any

import frappe
from frappe.utils import add_to_date, now_datetime

from ....connectors.base_connector import BaseAPIConnector
from ....utils.doctype_names import STANBIC_SETTINGS_DOCTYPE


class Baseurl(Enum):
    SANDBOX_URL = "https://api.connect.stanbicbank.co.ke/api/sandbox"
    LIVE_URL = "https://api.connect.stanbicbank.co.ke/api/sandbox"


class StanbicConnector(BaseAPIConnector):
    """
    Connector for Stanbic Bank PesaLink and Mobile Money APIs.
    Handles OAuth2 token retrieval, caching, and executing requests
    with full audit logging and error handling.
    """

    def __init__(self, settings_name):
        """
        Initialize the StanbicConnector.

        Args:
            settings_name: The name of the Stanbic Settings document.
        """
        super().__init__("Stanbic", STANBIC_SETTINGS_DOCTYPE, settings_name)
        self._token: str | None = None
        self._token_expirty: Any = None
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
        s = frappe.get_doc(STANBIC_SETTINGS_DOCTYPE, self.settings_name)
        self.client_id = s.client_id
        self.client_secret = s.get_password("client_secret")
        self._token = s.access_token
        self.scope = s.scope or "payments"
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
        if not self._token or not self._token_expiry:
            return False
        return now_datetime() < self._token_expiry

    def _get_token(self, manual_refresh=False) -> str:
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
