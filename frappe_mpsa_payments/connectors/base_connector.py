from __future__ import annotations

from copy import deepcopy
from typing import Literal

import frappe
import requests
from frappe.integrations.utils import create_request_log


def on_remote_error(provider: str, data, url: str, doctype: str, document_name: str):
    """
    Log and record a remote API error for the given provider and document.

    Args:
        provider: Name of the service provider (e.g., "Mpesa", "Stanbic").
        data: The error payload or response data.
        url: The full URL that was called.
        doctype: ERPNext DocType linked to this request.
        document_name: Name of the ERPNext document.
    """
    error_msg = (
        f"Remote error at {url} for {provider} {doctype} {document_name}: {data}"
    )
    frappe.log_error(
        title=f"{provider} Error",
        message=error_msg,
        reference_doctype=doctype,
        reference_name=document_name,
    )


def update_integration_request(
    integration_request: str,
    status: Literal["Completed", "Failed"],
    output: str | None = None,
    error: str | None = None,
) -> None:
    """
    Update an existing Integration Request record status, output, and error fields.

    Args:
        integration_request: Name of the Integration Request to update.
        status: New status ("Completed" or "Failed").
        output: Optional response payload to append.
        error: Optional error message to append.
    """
    doc = frappe.get_doc("Integration Request", integration_request, for_update=True)

    if error:
        doc.error = error if doc.error in (None, "null") else (doc.error + "\n" + error)

    if output:
        doc.output = (
            output if doc.output in (None, "null") else (doc.output + "\n" + output)
        )

    doc.status = status
    doc.save(ignore_permissions=True)


class ErrorObserver:
    """
    Observer that handles connector errors by updating the Integration Request
    and logging a fatal error before raising an exception.
    """

    def update(self, notifier: BaseAPIConnector):
        """
        Called when the notifier has an error set; updates Integration Request and logs.

        Args:
            notifier: The connector instance that encountered an error.
        """
        if notifier.error:
            on_remote_error(
                notifier.provider,
                notifier.error,
                notifier._url,
                notifier.doctype,
                notifier.document_name,
            )
            frappe.throw(
                "A fatal error occurred. Check the Error Log.",
                notifier.error,
                title=f"{notifier.provider} Fatal Error",
            )


class BaseAPIConnector:
    """
    Base class for HTTP-based integrations with built-in audit logging,
    error handling, and observer pattern.
    """

    def __init__(
        self,
        provider: str,
        settings_doctype: str,
        settings_name: str,
        timeout: float = 30.0,
    ):
        """
        Initialize the connector.

        Args:
            provider: Name of the external service (e.g., "Mpesa" or "Stanbic").
            settings_doctype: DocType storing integration settings.
            settings_name: Name of the settings document.
        """

        self.provider = provider
        self.settings_doctype = settings_doctype
        self.settings_name = settings_name
        self.timeout = timeout
        self.integration_request: str | None = None
        self.doctype: str | None = None
        self.document_name: str | None = None
        self.error: Exception | str = None
        self._observers = [ErrorObserver()]
        self._endpoint: str | None = None
        self._method: str | None = None
        self._payload: dict | None = None
        self._headers: dict = {}
        self._description: str | None = None
        self._reuse_existing: bool = False
        self._url: str | None = None
        self._use_form_data: bool = False

    def notify(self) -> None:
        for observer in self._observers:
            observer.update(self)

    def describe(self, desc: str) -> BaseAPIConnector:
        self._description = desc
        return self

    def set_endpoint(self, endpoint: str) -> BaseAPIConnector:
        self._endpoint = endpoint
        return self

    def set_method(self, method: str) -> BaseAPIConnector:
        self._method = method
        return self

    def set_payload(self, payload: dict) -> BaseAPIConnector:
        self._payload = payload
        return self

    def set_headers(self, headers: dict) -> BaseAPIConnector:
        self._headers.update(headers)
        return self

    def reuse_existing_request(self, flag: bool = True) -> BaseAPIConnector:
        self._reuse_existing = flag
        return self

    def _prepare_request_log(
        self, url: str, doctype: str | None = None, document_name: str | None = None
    ) -> None:
        """
        Create an Integration Request entry before making the HTTP call.

        Args:
            url: Full URL that will be called.
            doctype: Optional DocType to link.
            document_name: Optional document name to link.
        """

        self.doctype = doctype or self.settings_doctype
        self.document_name = document_name or self.settings_name

        scrubbed = deepcopy(self._payload or {})

        # 1.) Find all fields in that DocType declared as type “Password”
        try:
            meta = frappe.get_meta(self.doctype)
            password_fields = {
                f.fieldname for f in meta.fields if f.fieldtype == "Password"
            }
        except Exception:
            password_fields = set()

        # 2.) Mask every key that’s a real password field (or still catch anything with "secret"/"password")
        for key in list(scrubbed):
            if (
                key in password_fields
                or "secret" in key.lower()
                or "password" in key.lower()
            ):
                scrubbed[key] = "****"

        self.integration_request = create_request_log(
            data=scrubbed,
            request_description=self._description,
            is_remote_request=True,
            service_name=self.provider,
            request_headers=self._headers,
            url=url,
            reference_doctype=self.doctype,
            reference_docname=self.document_name,
        )

    def _finalize_success(self, data) -> None:
        """
        Mark the Integration Request as completed and store response data.

        Args:
            data: The successful JSON-decoded response.
        """
        update_integration_request(
            self.integration_request.name,
            status="Completed",
            output=str(data),
        )
        frappe.db.commit()

    def _finalize_error(self, data) -> None:
        """
        Mark the Integration Request as failed, store error, and log it.

        Args:
            data: The JSON-decoded error response or payload.
        """
        update_integration_request(
            self.integration_request.name,
            status="Failed",
            error=str(data),
        )
        frappe.db.commit()

    def use_form_data(self, flag: bool = True) -> BaseAPIConnector:
        """
        When True, send the payload as `data=…` instead of `json=…`.
        Useful for `application/x-www-form-urlencoded` calls.
        """
        self._use_form_data = flag
        return self

    def make_remote_call(
        self,
        base_url: str,
        doctype: str | None = None,
        document_name: str | None = None,
    ):
        """
        Execute the HTTP request, log both request and response,
        and handle success or error via observers.

        Args:
            base_url: The service's base URL (e.g. 'https://api.example.com').
            doctype: Optional DocType to tie this call to.
            document_name: Optional document name to tie this call to.

        Returns:
            The JSON-decoded response data, or None on exception.
        """
        self._url = f"{base_url.rstrip('/')}/{self._endpoint.lstrip('/')}"
        self._prepare_request_log(self._url, doctype, document_name)

        try:
            if self._use_form_data:
                resp = requests.request(
                    method=self._method,
                    url=self._url,
                    headers=self._headers,
                    data=self._payload,
                    timeout=self.timeout,
                )
            else:
                resp = requests.request(
                    method=self._method,
                    url=self._url,
                    headers=self._headers,
                    json=self._payload,
                    timeout=self.timeout,
                )
            data = resp.json()
        except Exception as e:
            self.error = e
            self.notify()
            return None

        if resp.status_code < 300:
            self._finalize_success(data)
        else:
            self.error = data
            self._finalize_error(data)
            self.notify()

        return data
