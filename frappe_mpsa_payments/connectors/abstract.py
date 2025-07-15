from abc import ABC, abstractmethod

from frappe.model.document import Document


class B2CConnector(ABC):
    """All B2C connectors must implement these methods."""

    @abstractmethod
    def send_b2c_request(self, request_doc: Document, callback_url: str) -> dict:
        """Trigger the B2C payment and return raw JSON response."""

    @abstractmethod
    def handle_callback(self, payload: dict) -> None:
        """Parse the provider's webhook/callback payload and update request_doc."""
