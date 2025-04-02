from frappe_mpsa_payments_app.models import MpesaExpressRequest
from django.dispatch import receiver
from core.signals import document_signals

@receiver(document_signals.on_submit, sender=MpesaExpressRequest)
def initiate_handler(sender, instance, **kwargs):
    # if created:  # Ensure this runs only when a new instance is created 
        # Prepare arguments for initiate_stk_push
        args = {
            "document_name": instance.id,
            "payment_gateway": instance.settings,
            "phone_number": instance.phone_number,
            "request_amount": instance.amount,
            "doctype": "MpesaExpressRequest",
            "reference_name": "Deo", 
        }

        try:
            from ...api.api import initiate_stk_push
            initiate_stk_push(data=args)
        except Exception as e:
            print(f"Error initiating STK push: {e}")
