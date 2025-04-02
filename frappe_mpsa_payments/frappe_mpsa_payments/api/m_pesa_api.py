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
    IntegrationRequest
)


import base64
import datetime
import json
import time
from .process_request import process_request
from .mpesa_response_handler import stk_push_on_success, transaction_status_on_success, balance_query_on_success
from typing import Any
from frappe_mpsa_payments.utils.encoding_initiator_password import (
    generate_security_credential,
)
from ...utils.utils import build_callback_url



@csrf_exempt
def balance_query_callback(request):
    """Handle M-Pesa balance query callback"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        result_data = data.get("Result")
        
        if not result_data:
            return JsonResponse({'error': "Missing 'Result' in callback response"}, status=400)

        result_code = result_data.get("ResultCode")
        result_desc = result_data.get("ResultDesc", "No description provided")

        if result_code is None:
            return JsonResponse({'error': "Missing 'ResultCode' in callback response"}, status=400)

        conversation_id = result_data.get("ConversationID")
        if not conversation_id:
            return JsonResponse({'error': "ConversationID missing in callback response"}, status=400)

        try:
            integration_request = IntegrationRequest.objects.filter(
                output__contains=conversation_id
            ).first()
            
            if not integration_request:
                return JsonResponse({
                    'error': f"No matching Integration Request found for ConversationID: {conversation_id}"
                }, status=404)

            if str(result_code) != "0":
                integration_request.status = "Failed"
                integration_request.error = json.dumps(result_data, indent=4)
                integration_request.save()
                return JsonResponse({
                    'error': f"ResultCode: {result_code}, ResultDesc: {result_desc}"
                }, status=400)

            integration_request.output = json.dumps(result_data, indent=4)
            integration_request.status = "Completed"
            integration_request.save()

            account_balance = None
            result_params = result_data.get("ResultParameters", {}).get("ResultParameter", [])
            for param in result_params:
                if param.get("Key") == "AccountBalance":
                    account_balance = param.get("Value")
                    break

            if not account_balance:
                return JsonResponse({'error': "AccountBalance missing in callback response"}, status=400)

            settings_docname = integration_request.reference_docname
            if not settings_docname:
                return JsonResponse({
                    'error': "Reference document name missing in Integration Request"
                }, status=400)

            settings = MpesaSettings.objects.get(pk=settings_docname)
            update_account_balances(account_balance, settings)

            return JsonResponse({'status': 'success', 'message': 'Balance updated successfully'})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)


def update_account_balances(account_balance, settings):
    """Update account balances in MpesaSettings"""
    if not account_balance or not settings:
        raise ValueError("Missing required parameters: account_balance or settings")

    account_mapping = {
        "Working Account": "working_account",
        "Utility Account": "utility_account",
        "Merchant Account": "merchant_account",
        "Charges Paid Account": "charges_paid_account",
        "Airtime Purchase Account": "airtime_purchase_account",
        "Loan Disbursement Account": "loan_disbursement_account",
        "Organization Settlement Account": "organization_settlement_account",
        "Advanced Deduction Account": "advanced_deduction_account",
        "Savings Deduction Account": "savings_deduction_account"
    }

    balances = account_balance.split("&") 
    for balance in balances:
        details = balance.split("|") 
        if len(details) >= 3:
            account_name = details[0]
            try:
                available_balance = float(details[2]) 
            except ValueError:
                available_balance = 0.0 
                
            field_name = account_mapping.get(account_name)
            if field_name:
                setattr(settings, field_name, available_balance)
    
    settings.save()
    return {"status": "success", "message": "Account balances updated successfully"}


def get_account_balance(request, name):
    """Call account balance API to send the request to the Mpesa Servers."""
    try:
        settings = MpesaSettings.objects.get(pk=name)
        
        # In Django, you might store certificates differently - this is a placeholder
        cert_url = settings.sandbox_certificate if settings.sandbox else settings.production_certificate
            
        security_credential = generate_security_credential(
            settings.initiator_password,
            cert_url
        )

        endpoint = "/mpesa/accountbalance/v1/query"
        
        callback_url = build_callback_url("mpesa.balance_query_callback")
        timeout_url = build_callback_url("mpesa.handle_queue_timeout")
                
        payload = {
            "Initiator": settings.initiator_name,
            "SecurityCredential": security_credential, 
            "CommandID": "AccountBalance",
            "PartyA": settings.business_shortcode,
            "IdentifierType": "4",
            "Remarks": "Balance",
            "QueueTimeOutURL": timeout_url,
            "ResultURL": callback_url,
        }

        response = process_request(
            endpoint=endpoint,
            method="POST",
            payload=payload,
            success_callback=balance_query_on_success,
            request_description="Mpesa Balance Query",
            doctype=MPESA_SETTINGS_DOCTYPE,
            document_name=name,
            settings_name=name,
        )
        return JsonResponse(response)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def check_transaction_status(request, name):
    """Check the status of a transaction by its name."""
    try:
        express_request = MpesaExpressRequest.objects.get(pk=name)
        settings = express_request.settings

        endpoint = "/mpesa/stkpushquery/v1/query"
        time_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        payload = {
            "BusinessShortCode": settings.business_shortcode,
            "Password": generate_request_password(settings, time_str),
            "Timestamp": time_str,
            "CheckoutRequestID": express_request.checkout_request_id,
        }

        response = process_request(
            endpoint=endpoint,
            method="POST",
            payload=payload,
            success_callback=transaction_status_on_success,
            error_callback=transaction_status_error_callback,
            request_description="Mpesa Transaction Status Query",
            doctype=MPESA_EXPRESS_REQUEST_DOCTYPE,
            document_name=express_request.name,
            settings_name=express_request.settings.name,
            reuse_existing_request=True,
        )
        return JsonResponse(response)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def transaction_status_error_callback(response, payload, document_name, **kwargs):
    time.sleep(5)
    # In Django, you might use Celery or Django Background Tasks for this
    from .tasks import check_transaction_status_task
    check_transaction_status_task.delay(document_name)
    return None


def initiate_stk_push(data):
    """Generate STK push by making an API call to the STK push API."""
    try:
        print("Initiating STK Push...")
        print(f"Data received: {data}")
        payment_gateway = data.get('payment_gateway')
        phone_number = data.get('phone_number')
        request_amount = data.get('request_amount')
        reference_name = data.get('reference_name', 'Online Payment')

        required_fields = ["payment_gateway", "phone_number", "request_amount"]
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            return {'error': f"Missing required fields: {', '.join(missing_fields)}"}, 400

        callback_url = build_callback_url("mpesa.stk_push_callback")
        mpesa_settings = MpesaSettings.objects.get(pk=payment_gateway[6:])
        mobile_number = sanitize_mobile_number(phone_number)
        amount = request_amount
        business_shortcode = mpesa_settings.business_shortcode
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        payload = {
            "BusinessShortCode": business_shortcode,
            "Password": generate_request_password(mpesa_settings, timestamp),
            "Timestamp": timestamp,
            "Amount": amount,
            "PartyA": int(mobile_number),
            "PartyB": business_shortcode,
            "PhoneNumber": int(mobile_number),
            "CallBackURL": callback_url,
            "AccountReference": reference_name,
            "TransactionDesc": reference_name,
            "TransactionType": "CustomerPayBillOnline"
            if mpesa_settings.paybill_type == "Pay Bill"
            else "CustomerBuyGoodsOnline",
        }

        endpoint = "/mpesa/stkpush/v1/processrequest"
        
        print(f"STK Push Payload: {json.dumps(payload, indent=4)}")
        print(f"STK Push Endpoint: {endpoint}")
        print(f"STK Push Callback URL: {callback_url}")
        
        
        response = process_request(
            endpoint=endpoint,
            method="POST",
            payload=payload,
            success_callback=stk_push_on_success,
            request_description="Mpesa STK Push",
            doctype=data.get("doctype", "MpesaExpressRequest"),
            document_name=data.get("document_name", mpesa_settings.name),
            settings_name=mpesa_settings.name,
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
        f"{settings.business_shortcode}{settings.get_password('online_passkey')}{time}".encode()
        ).decode()
    
@csrf_exempt
def stk_push_callback(request):
    """Verify the transaction result received via callback from STK."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        transaction_response = data.get("Body", {}).get("stkCallback", {})

        checkout_request_id = transaction_response.get("CheckoutRequestID")
        if not isinstance(checkout_request_id, str):
            return JsonResponse({'error': 'Invalid Checkout Request ID'}, status=400)

        result_code = transaction_response.get("ResultCode")
        result_desc = transaction_response.get("ResultDesc")

        callback_metadata = transaction_response.get("CallbackMetadata", {}).get("Item", [])
        metadata_dict = {item.get("Name"): item.get("Value") for item in callback_metadata if "Value" in item}

        status = "Completed" if str(result_code) == "0" else "Failed"

        try:
            request_doc = MpesaExpressRequest.objects.get(checkout_request_id=checkout_request_id)
        except MpesaExpressRequest.DoesNotExist:
            return JsonResponse({'error': 'Transaction not found'}, status=404)

        if status == "Completed" and request_doc.status != "Completed" and request_doc.reference_doctype == "PaymentRequest":
            # In Django, you would implement your payment processing logic here
            pass

        request_doc.result_code = result_code
        request_doc.result_desc = result_desc
        request_doc.transaction_id = metadata_dict.get("MpesaReceiptNumber")
        request_doc.status = status
        request_doc.save()

        return JsonResponse({'status': 'success'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_token(app_key, app_secret, base_url):
    """Get M-Pesa API token"""
    authenticate_uri = "/oauth/v1/generate?grant_type=client_credentials"
    authenticate_url = f"{base_url}{authenticate_uri}"

    response = requests.get(authenticate_url, auth=HTTPBasicAuth(app_key, app_secret))
    return response.json().get("access_token")


@csrf_exempt
def confirmation(request):
    """Handle M-Pesa C2B confirmation"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        
        with transaction.atomic():
            doc = MpesaC2BPaymentRegister(
                transactiontype=data.get("TransactionType"),
                transid=data.get("TransID"),
                transtime=data.get("TransTime"),
                transamount=data.get("TransAmount"),
                businessshortcode=data.get("BusinessShortCode"),
                billrefnumber=data.get("BillRefNumber"),
                invoicenumber=data.get("InvoiceNumber"),
                orgaccountbalance=data.get("OrgAccountBalance"),
                thirdpartytransid=data.get("ThirdPartyTransID"),
                msisdn=data.get("MSISDN"),
                firstname=data.get("FirstName"),
                middlename=data.get("MiddleName"),
                lastname=data.get("LastName")
            )
            doc.save()

        context = {"ResultCode": 0, "ResultDesc": "Accepted"}
        return JsonResponse(context)

    except Exception as e:
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Rejected"}, status=400)


@csrf_exempt
def validation(request):
    """Handle M-Pesa C2B validation"""
    context = {"ResultCode": 0, "ResultDesc": "Accepted"}
    return JsonResponse(context)


def get_mpesa_mode_of_payment(request, company):
    """Get M-Pesa modes of payment for a company"""
    modes = MpesaC2BPaymentRegister.objects.filter(
        company=company,
        register_status="Success"
    ).values_list('mode_of_payment', flat=True).distinct()
    
    return JsonResponse({'modes_of_payment': list(modes)})


def get_mpesa_draft_c2b_payments(request):
    """Get draft M-Pesa C2B payments"""
    company = request.GET.get('company')
    full_name = request.GET.get('full_name')
    mode_of_payment = request.GET.get('mode_of_payment')
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    filters = {"company": company, "docstatus": 0}
    order_by = "-posting_date", "-posting_time"

    if mode_of_payment:
        filters["mode_of_payment"] = mode_of_payment

    if full_name:
        filters["full_name__icontains"] = full_name

    if from_date and to_date:
        filters["posting_date__range"] = [from_date, to_date]
    elif from_date:
        filters["posting_date__gte"] = from_date
    elif to_date:
        filters["posting_date__lte"] = to_date

    payments = MpesaC2BPaymentRegister.objects.filter(**filters).order_by(*order_by).values(
        "name", "transid", "company", "msisdn", "full_name", 
        "posting_date", "posting_time", "transamount"
    )
    
    return JsonResponse({'payments': list(payments)})


@csrf_exempt
def handle_transaction_status_result(request):
    """Handle the transaction status response from Mpesa"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        response_data = json.loads(request.body)

        integration_request = IntegrationRequest(
            is_remote_request=True,
            integration_request_service="Mpesa Transaction Status Result Callback",
            reference_doctype="MpesaC2BPaymentRegister",
            status="Queued",
            data=json.dumps(response_data),
            url=request.build_absolute_uri(),
            method="POST"
        )
        integration_request.save()

        # In Django, you would use Celery or similar for background tasks
        from .tasks import process_mpesa_integration_request_task
        process_mpesa_integration_request_task.delay(integration_request.id)

        return JsonResponse({"status": "queued", "message": "Transaction queued for processing"})
    
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"Webhook error: {str(e)}"}, status=500)


def process_mpesa_integration_request(integration_request_id):
    """Process the Mpesa Integration Request"""
    try:
        integration_request = IntegrationRequest.objects.get(pk=integration_request_id)
        response_data = json.loads(integration_request.data)
        result_data = response_data.get("Result", {})
        result_parameters = result_data.get("ResultParameters", {}).get("ResultParameter", [])
        result_params = {param.get("Key", ""): param.get("Value", "") for param in result_parameters if "Key" in param}
        
        result_code = result_data.get("ResultCode", None)
        receipt_no = result_params.get("ReceiptNo", "")
        business_shortcode = result_params.get("CreditPartyName", "").split("-")

        if result_code == 0:
            if MpesaC2BPaymentRegister.objects.filter(transid=receipt_no).exists():
                error_msg = f"Duplicate transaction: Receipt No {receipt_no} already exists"
                integration_request.status = "Failed"
                integration_request.output = error_msg
                integration_request.save()
                
                return JsonResponse({"status": "error", "message": error_msg})

            with transaction.atomic():
                debit_party = result_params.get("DebitPartyName", "").split(" - ")
                name_parts = debit_party[1].split(" ") if len(debit_party) > 1 else ["", "", ""]

                mpesa_doc = MpesaC2BPaymentRegister(
                    full_name=result_params.get("DebitPartyName", ""),
                    transactiontype=result_params.get("ReasonType", ""),
                    transid=result_params.get("ReceiptNo", ""),
                    transtime=result_params.get("InitiatedTime", ""),
                    transamount=float(result_params.get("Amount", 0.0)),
                    businessshortcode=business_shortcode[0],
                    billrefnumber=result_params.get("ReceiptNo", ""),
                    invoicenumber=result_params.get("TransactionID", ""),
                    orgaccountbalance=result_params.get("DebitAccountType", ""),
                    thirdpartytransid=result_params.get("OriginatorConversationID", ""),
                    msisdn=debit_party[0] if len(debit_party) > 0 else "",
                    firstname=name_parts[0],
                    middlename=name_parts[1] if len(name_parts) > 1 else "",
                    lastname=name_parts[-1] if len(name_parts) > 2 else ""
                )
                mpesa_doc.save()

                integration_request.status = "Completed"
                integration_request.output = "Transaction processed successfully"
                integration_request.reference_document = mpesa_doc.name
                integration_request.save()

            return JsonResponse({
                "status": "success", 
                "message": "Transaction processed successfully",
                "doc_name": mpesa_doc.name
            })
        
        else:
            error_msg = "Transaction failed with non-zero result code"
            integration_request.status = "Failed"
            integration_request.output = error_msg
            integration_request.save()

            return JsonResponse({"status": "error", "message": error_msg})

    except Exception as e:
        error_message = f"Mpesa Processing Error: {str(e)}"
        integration_request.status = "Failed"
        integration_request.output = error_message
        integration_request.save()

        return JsonResponse({"status": "error", "message": error_message}, status=500)


@csrf_exempt
def handle_queue_timeout(request):
    """Handle the timeout response from Mpesa."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        response_data = json.loads(request.body)
        return JsonResponse({
            "status": "timeout", 
            "message": "Timeout response logged successfully."
        })

    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error", 
            "message": "Invalid JSON received."
        }, status=400)

    except Exception as e:
        return JsonResponse({
            "status": "error", 
            "message": str(e)
        }, status=500)


@csrf_exempt
def verify_transaction(request):
    """Verify the transaction result received via callback from stk."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        transaction_response = data.get("Body", {}).get("stkCallback", {})

        checkout_id = transaction_response.get("CheckoutRequestID", "")
        if not isinstance(checkout_id, str):
            return JsonResponse({'error': 'Invalid Checkout Request ID'}, status=400)

        try:
            integration_request = IntegrationRequest.objects.get(pk=checkout_id)
        except IntegrationRequest.DoesNotExist:
            return JsonResponse({'error': 'Integration request not found'}, status=404)

        transaction_data = json.loads(integration_request.data)
        total_paid = 0  
        success = False

        if transaction_response.get("ResultCode") == 0:
            if integration_request.reference_doctype and integration_request.reference_docname:
                try:
                    item_response = transaction_response.get("CallbackMetadata", {}).get("Item", [])
                    amount = next((item["Value"] for item in item_response if item.get("Name") == "Amount"), 0)
                    mpesa_receipt = next((item["Value"] for item in item_response if item.get("Name") == "MpesaReceiptNumber"), "")

                    # In Django, you would implement your payment processing logic here
                    # This is a placeholder for the Frappe-specific logic
                    # pr = frappe.get_doc(integration_request.reference_doctype, integration_request.reference_docname)

                    # Simplified version for Django:
                    total_paid = amount
                    success = True

                    integration_request.status = "Completed"
                    integration_request.save()

                except Exception as e:
                    integration_request.status = "Failed"
                    integration_request.save()
                    return JsonResponse({'error': str(e)}, status=500)

        else:
            integration_request.status = "Failed"
            integration_request.save()

        return JsonResponse({
            "amount": total_paid,
            "success": success,
            "failure_message": (
                transaction_response.get("ResultDesc", "")
                if transaction_response.get("ResultCode", 1) != 0
                else ""
            ),
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)