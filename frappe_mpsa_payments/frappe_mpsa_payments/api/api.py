import base64
import datetime
import json
import time
from typing import Any, Dict, Optional
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.conf import settings
import requests
from requests.auth import HTTPBasicAuth
from ...utils.model_imports import (
    MpesaSettings,
    MpesaExpressRequest,
    MpesaC2BPaymentRegister,
    IntegrationRequest,
    PaymentRequest, 
    PaymentEntry, 
    Company
)

import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


import base64
import datetime
import json
import time
from .process_request import process_request
from ...utils.utils import build_callback_url
from .mpesa_response_handler import stk_push_on_success



def initiate_stk_push(data):
    """Generate STK push by making an API call to the STK push API."""
    try: 
        payment_gateway = data.get('payment_gateway', "Mpesa")
        phone_number = data.get('phone_number')
        request_amount = data.get('request_amount')
        reference_name = data.get('reference_name', 'Online Payment')

        required_fields = ["payment_gateway", "phone_number", "request_amount"]
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return {'error': f"Missing required fields: {', '.join(missing_fields)}"}, 400

        callback_url = build_callback_url("frappe_mpsa_payments.frappe_mpsa_payments.api.response_handler.STKPushCallback/")
        mpesa_settings = MpesaSettings.objects.get(pk=payment_gateway.id)  
        mobile_number = sanitize_mobile_number(phone_number)
        amount = request_amount
        business_shortcode = mpesa_settings.business_shortcode
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        payload = { 
            "BusinessShortCode": business_shortcode,
            "Password": generate_request_password(mpesa_settings, timestamp),
            "Timestamp": timestamp,
            "Amount": str(int(amount)), 
            "PartyA": mobile_number, 
            "PartyB": mpesa_settings.till_number, 
            "PhoneNumber": mobile_number,
            "CallBackURL": callback_url,
            "AccountReference": reference_name,
            "TransactionDesc": reference_name,
            "TransactionType": "CustomerPayBillOnline"
            if mpesa_settings.paybill_type == "Pay Bill"
            else "CustomerBuyGoodsOnline",
        }

        endpoint = "/mpesa/stkpush/v1/processrequest"
        
        
        
        response = process_request(
            endpoint=endpoint,
            method="POST",
            payload=payload,
            success_callback=stk_push_on_success,
            request_description="Mpesa STK Push",
            doctype=data.get("doctype", "MpesaExpressRequest"),
            document_name=data.get("document_name", mpesa_settings.id), 
            settings_name=mpesa_settings.id,
        )
        return response

    except Exception as e:
        print(f"Error initiating STK push: {e}")
        return {'error': str(e)}, 500

    

def sanitize_mobile_number(number: str) -> str:
    """Strip all non-digit characters, take the last 9 digits, and add country code."""
    sanitized_number = ''.join(filter(str.isdigit, number))[-9:]
    return "254" + sanitized_number

def generate_request_password(settings: dict, time: str ) -> str:
    """Generate the password for making a request to the M-Pesa API."""
    return base64.b64encode(
        f"{settings.business_shortcode}{settings.online_passkey}{time}".encode()  
        ).decode()
    




@csrf_exempt
def stk_push_callback(request):
    """
    M-Pesa STK Push callback handler that creates a Payment Entry
    """
    if request.method != 'POST':
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        callback_data = data.get('Body', {}).get('stkCallback', {})
        
        checkout_request_id = callback_data.get('CheckoutRequestID')
        result_code = callback_data.get('ResultCode')
        result_desc = callback_data.get('ResultDesc', 'No description')
        
        # Extract metadata
        metadata = {item['Name']: item['Value'] 
                  for item in callback_data.get('CallbackMetadata', {}).get('Item', []) 
                  if 'Value' in item}
        
        status = 'Completed' if str(result_code) == '0' else 'Failed'
        
        with transaction.atomic():
            try:
                express_request = MpesaExpressRequest.objects.select_for_update().get(
                    checkout_request_id=checkout_request_id
                )
            except MpesaExpressRequest.DoesNotExist:
                logger.error(f"MpesaExpressRequest not found: {checkout_request_id}")
                return JsonResponse({"ResultCode": 1, "ResultDesc": "Request not found"}, status=404)

            # Update express request
            express_request.result_code = result_code
            express_request.result_desc = result_desc
            express_request.transaction_id = metadata.get('MpesaReceiptNumber')
            express_request.status = status
            express_request.save()

            if status == 'Completed' and express_request.reference_doctype == 'PaymentRequest':
                try:
                    payment_request = PaymentRequest.objects.select_for_update().get(
                        pk=express_request.reference_name
                    )
                    
                    # Create Payment Entry
                    payment_entry = PaymentEntry(
                        payment_type='Receive',
                        company=Company.objects.get_default(),
                        posting_date=timezone.now().date(),
                        mode_of_payment=payment_request.mode_of_payment,
                        party_type=payment_request.party_type,
                        party=payment_request.party,
                        paid_amount=Decimal(metadata.get('Amount', 0)),
                        received_amount=Decimal(metadata.get('Amount', 0)),
                        reference_no=metadata.get('MpesaReceiptNumber'),
                        reference_date=timezone.now().date(),
                        remarks=f"M-Pesa payment for {payment_request.name}",
                        payment_request=payment_request
                    )
                    payment_entry.save()
                    
                    # Update payment request status
                    payment_request.status = 'Paid'
                    payment_request.save()
                    
                    logger.info(f"Created Payment Entry {payment_entry.id} for M-Pesa payment {express_request.id}")

                except Exception as e:
                    logger.error(f"Error creating payment entry: {str(e)}", exc_info=True)
                    raise

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})

    except json.JSONDecodeError:
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"STK callback processing failed: {str(e)}", exc_info=True)
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Processing error"}, status=500)