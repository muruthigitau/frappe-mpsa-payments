from django.utils import timezone
from django.db import transaction
import logging
from ...utils.model_imports import MpesaExpressRequest
from decimal import Decimal

logger = logging.getLogger(__name__)

def stk_push_on_success(response: dict, payload: dict, document_name: str, **kwargs) -> None:
    """
    Handle successful STK push response
    Args:
        response: API response dictionary
        payload: Original request payload
        document_name: Name of the document to update/create
        **kwargs: Additional context including settings_name, doctype, etc.
    """
    try:
        with transaction.atomic():
            # Prepare fields data
            fields = {
                'merchant_request_id': response.get('MerchantRequestID', ''),
                'checkout_request_id': response.get('CheckoutRequestID', ''),
                'response_code': response.get('ResponseCode', ''),
                'response_description': response.get('ResponseDescription', ''),
                'result_code': response.get('ResultCode', ''),
                'result_desc': response.get('ResultDesc', ''),
                'amount': Decimal(str(payload.get('Amount', 0.0))),
                'phone_number': payload.get('PhoneNumber', ''),
                'account_reference': response.get('AccountReference', ''),
                'transaction_desc': response.get('TransactionDesc', ''),
                'transaction_id': response.get('MpesaReceiptNumber', ''),
                'timestamp': timezone.now(),
            }

            doctype = kwargs.get('doctype', '')

            if doctype == 'MpesaExpressRequest':
                # Update existing record
                try:
                    express_request = MpesaExpressRequest.objects.select_for_update().get(pk=document_name)
                    for key, value in fields.items():
                        setattr(express_request, key, value)
                    express_request.save()
                    logger.info(f"Mpesa Express Request updated for {document_name}")
                except MpesaExpressRequest.DoesNotExist:
                    logger.error(f"MpesaExpressRequest {document_name} not found")
                    raise
            else:
                # Create new record
                express_request = MpesaExpressRequest(**fields)
                express_request.save()
                logger.info(f"Mpesa Express Request created with ID {express_request.id}")

            # In Django, you might use Django Channels or similar for realtime updates
            # Here we'll just log the update
            logger.debug(f"Refresh needed for MpesaExpressRequest {document_name}")

            # If you need to check transaction status later, you could use Celery:
            # from .tasks import check_transaction_status
            # check_transaction_status.delay(document_name)

    except Exception as e:
        logger.error(f"STK Push Success Error for {document_name}: {str(e)}", exc_info=True)
        raise