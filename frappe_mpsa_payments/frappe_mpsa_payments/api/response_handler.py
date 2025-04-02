from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.db import transaction
from decimal import Decimal
import json
import logging
from django.utils import timezone
from ...utils.model_imports import MpesaExpressRequest, Payment

logger = logging.getLogger(__name__)

class STKPushCallback(APIView):
    """
    M-Pesa STK Push Callback API View 
    """
    permission_classes = [AllowAny]  # Allow unrestricted access

    def get(self, request, *args, **kwargs):
        """
        Handle GET requests.
        """
        return Response({"message": "STK Callback GET request working!"})

    def post(self, request, *args, **kwargs):
        """
        Handle M-Pesa STK push callback.
        """
        try:
            # Parse and validate incoming data
            try:
                data = json.loads(request.body)
                logger.info(f"Received STK callback data: {data}")
            except json.JSONDecodeError:
                return Response(
                    {"ResultCode": 1, "ResultDesc": "Invalid JSON"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Extract callback details
            callback_data = data.get('Body', {}).get('stkCallback', {})
            checkout_request_id = callback_data.get('CheckoutRequestID')
            result_code = callback_data.get('ResultCode')
            result_desc = callback_data.get('ResultDesc', 'No description')

            if not checkout_request_id:
                return Response(
                    {"ResultCode": 1, "ResultDesc": "Missing CheckoutRequestID"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Extract metadata
            metadata = {
                item['Name']: item['Value']
                for item in callback_data.get('CallbackMetadata', {}).get('Item', [])
                if 'Value' in item
            }

            status_code = 'Completed' if str(result_code) == '0' else 'Failed'

            # Process the transaction
            with transaction.atomic():
                try:
                    express_request = MpesaExpressRequest.objects.select_for_update().get(
                        checkout_request_id=checkout_request_id
                    )
                except MpesaExpressRequest.DoesNotExist:
                    logger.error(f"MpesaExpressRequest not found: {checkout_request_id}")
                    return Response(
                        {"ResultCode": 1, "ResultDesc": "Request not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )

                # Update STK request status
                express_request.result_code = result_code
                express_request.result_desc = result_desc
                express_request.transaction_id = metadata.get('MpesaReceiptNumber')
                express_request.status = status_code
                express_request.save()

                # Process payment if transaction is successful
                if status_code == 'Completed' :
                    self._process_payment(express_request, metadata)

            return Response({"ResultCode": 0, "ResultDesc": "Success"})

        except Exception as e:
            logger.error(f"STK callback processing failed: {str(e)}", exc_info=True)
            return Response(
                {"ResultCode": 1, "ResultDesc": "Server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_payment(self, express_request, metadata):
        """
        Helper method to process payment and create a payment entry.
        """
        try:
            payment_entry = Payment(
                amount=express_request.amount,
                order_id=express_request.reference_name,
                transaction_id=express_request.transaction_id,
                payment_method='M-Pesa',
                date=timezone.now().date(),
            )
            payment_entry.save()
            
            
            logger.info(f"Created Payment Entry {payment_entry.id} for M-Pesa payment {express_request.id}")

        except Exception as e:
            logger.error(f"Error creating payment entry: {str(e)}", exc_info=True)
            raise
