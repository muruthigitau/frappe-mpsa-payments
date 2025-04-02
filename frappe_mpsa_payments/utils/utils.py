from contextlib import contextmanager
from datetime import datetime
from typing import Generator, Optional
from urllib.parse import urlparse
from django.conf import settings
from django.urls import reverse
from django.http import HttpRequest
from .model_imports import (
    PaymentGateway,
    PaymentGatewayAccount,
    Account,
)

# Constants
ACCESS_TOKENS_DOCTYPE = "AccessToken"


def create_payment_gateway(
    gateway: str, 
    settings: Optional[str] = None, 
    controller: Optional[str] = None
) -> None:
    """Create a payment gateway if it doesn't exist"""
    if not PaymentGateway.objects.filter(gateway=gateway).exists():
        payment_gateway = PaymentGateway(
            gateway=gateway,
            gateway_settings=settings,
            gateway_controller=controller
        )
        payment_gateway.save()


@contextmanager
def erpnext_app_import_guard() -> Generator:
    """Context manager to handle ERPNext app import errors"""
    marketplace_link = "https://frappecloud.com/marketplace/apps/erpnext"
    github_link = "https://github.com/frappe/erpnext"
    msg = f"ERPNext app is not installed. Please install it from {marketplace_link} or {github_link}"
    
    try:
        yield
    except ImportError as e:
        raise ImportError(msg) from e


def save_access_token(
    token: str,
    expiry_time: str | datetime,
    fetch_time: str | datetime,
    associated_setting: str,
    doctype: str = ACCESS_TOKENS_DOCTYPE,
) -> bool:
    """Save an access token to the database"""
    pass
    # doc = AccessToken(
    #     associated_settings=associated_setting,
    #     access_token=token,
    #     expiry_time=expiry_time,
    #     token_fetch_time=fetch_time
    # )

    # try:
    #     doc.save()
    #     return True
    # except Exception as e:
    #     raise Exception("Error Encountered while saving access token") from e


def get_payment_gateway_controller(payment_gateway: str):
    """Return payment gateway controller"""
    try:
        gateway = PaymentGateway.objects.get(gateway=payment_gateway)
    except PaymentGateway.DoesNotExist:
        raise ValueError(f"Payment Gateway {payment_gateway} not found")

    if gateway.gateway_controller is None:
        try:
            # Assuming you have a model named {gateway}Settings
            settings_model = globals().get(f"{payment_gateway}Settings")
            if settings_model is None:
                raise ValueError(f"{payment_gateway} Settings model not found")
            return settings_model.objects.first()
        except Exception as e:
            raise ValueError(f"{payment_gateway} Settings not found") from e
    else:
        try:
            # Assuming gateway_settings is the model name and gateway_controller is the ID
            settings_model = globals().get(gateway.gateway_settings)
            if settings_model is None:
                raise ValueError(f"{gateway.gateway_settings} model not found")
            return settings_model.objects.get(pk=gateway.gateway_controller)
        except Exception as e:
            raise ValueError(f"{gateway.gateway_settings} Settings not found") from e


def create_payment_gateway_account(gateway: str, payment_channel: str = "Email", company: Optional[str] = None):
    """Create a payment gateway account"""
    from .setup_utils import create_bank_account  # Assuming you have this utility

    # company = company or GlobalDefaults.objects.first().default_company
    if not company:
        return None

    # Try to get existing account (translated name)
    bank_account = Account.objects.filter(
        account_name=gateway,
        company=company
    ).values('id', 'account_currency').first()

    if not bank_account:
        # Try with untranslated name
        bank_account = Account.objects.filter(
            account_name=gateway,
            company=company
        ).values('id', 'account_currency').first()

    if not bank_account:
        # Create new account
        bank_account_data = {
            'company_name': company,
            'bank_account': gateway
        }
        bank_account = create_bank_account(bank_account_data)
        if not bank_account:
            raise ValueError("Payment Gateway Account not created, please create one manually.")

    # Check if payment gateway account already exists
    if PaymentGatewayAccount.objects.filter(
        payment_gateway=gateway,
        currency=bank_account['account_currency']
    ).exists():
        return None

    try:
        PaymentGatewayAccount.objects.create(
            is_default=True,
            payment_gateway=gateway,
            payment_account=bank_account['id'],
            currency=bank_account['account_currency'],
            payment_channel=payment_channel
        )
    except Exception as e:
        # Handle duplicate entry if needed
        pass


def build_callback_url(endpoint: str) -> str:
    """Build a callback URL for API endpoints"""
    # base_url = request.build_absolute_uri('/')[:-1]  # Get base URL without trailing slash
    # parsed_url = urlparse(base_url)

    # if not (parsed_url.hostname == "localhost" or parsed_url.hostname.replace(".", "").isdigit()):
    #     base_url = f"{parsed_url.scheme}://{parsed_url.hostname}"

    # # Assuming your API endpoints are structured with 'api' prefix
    return f"https://f10f-102-213-49-42.ngrok-free.app/apis/method/{endpoint}" 