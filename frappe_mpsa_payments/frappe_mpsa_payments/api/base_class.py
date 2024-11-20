from __future__ import annotations

from abc import ABC, abstractmethod

import frappe

from ...utils.helpers import update_integration_request


class ConnectorAbstractClass(ABC):
    """Abstract Base class for Connector Classes"""

    @abstractmethod
    def attach(self, observer: Observer) -> None:
        """Attach Observers

        Args:
            observer (Observer): The observer to attach
        """

    @abstractmethod
    def notify(self) -> None:
        """Notify all registered observers"""


class ConnectorBaseClass(ConnectorAbstractClass):
    """Base class for Connector Classes"""

    def __init__(self) -> None:
        self.error: str | Exception | None = None
        self.integration_request: str | None = None

        self._observers: list[Observer] = []

    def attach(self, observer: Observer) -> None:
        """Attach Observers

        Args:
            observer (Observer): The observer to attach
        """
        self._observers.append(observer)

    def notify(self) -> None:
        """Notify all registered observers"""
        for observer in self._observers:
            observer.update(self)


class Observer(ABC):
    """Observer Abstract Class"""

    @abstractmethod
    def update(self, notifier: ConnectorBaseClass) -> None:
        """Method that reacts to specific state in the notifier when called

        Args:
            notifier (ConnectorBaseClass): The Notifier (calling class)
        """


class ErrorObserver(Observer):
    """Error Observer concrete class"""

    def update(self, notifier: ConnectorBaseClass) -> None:
        if notifier.error:
            frappe.log_error(
                title="HTTPError",
                message=notifier.error,
            )
            update_integration_request(
                notifier.integration_request,
                status="Failed",
                error=str(notifier.error),
            )
            frappe.throw(
                str(notifier.error),
                frappe.DataError,
                title="HTTPError",
            )
