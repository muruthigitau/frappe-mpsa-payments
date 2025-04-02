from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.db import transaction
from decimal import Decimal
import logging
from django.utils import timezone
from ...utils.model_imports import (
    Order, Customers, Locations, 
    MpesaExpressRequest, Payment, Product
)

logger = logging.getLogger(__name__)

class OrderAPI(APIView):
    """
    API for creating and retrieving orders with customer, location, and product data.
    """
    permission_classes = [AllowAny]  # Adjust permissions as needed

    def get(self, request, *args, **kwargs):
        """
        Retrieve complete order details using query parameters.
        Example: GET /orders/?order_id=5
        """
        try:
            order_id = request.query_params.get('order_id')  # Get order_id from query params

            if not order_id:
                return Response({"error": "Order ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            order = Order.objects.get(id=order_id)
            if not order:
                return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

            
            # Serialize order with all fields
            order_data = {
                'id': order.id,
                'total': str(order.total),
                'shipping': str(order.shipping),
                'status': order.status,
                'delivery_option': order.delivery_option,
                'notes': order.notes if order.notes else None,
                'created': order.created,
                'modified': order.modified,
                'items': [self._serialize_product(item) for item in order.items.all()]
            }

            # Serialize customer with all fields
            customer_data = {
                'id': order.customer.id,
                'first_name': order.customer.first_name,
                'last_name': order.customer.last_name,
                'phone_number': order.customer.phone_number,
                'email': order.customer.email,
                'additional_phone': order.customer.additional_phone if order.customer.additional_phone else None,
                'created': order.customer.created,
                'modified': order.customer.modified
            }

            # Serialize location with all fields
            location_data = {
                'id': order.location.id,
                'street_address': order.location.street_address,
                'city': order.location.city,
                'name': order.location.name,
                'description': order.location.description if order.location.description else None,
                'type': order.location.type,
                'created': order.location.created,
                'modified': order.location.modified
            }

            response_data = {
                'order': order_data,
                'customer': customer_data,
                'location': location_data
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error retrieving order {order_id}: {str(e)}", exc_info=True)
            return Response(
                {"error": "Server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        """
        Create a new order with complete customer, location, and product data.
        """
        try:
            data = request.data
            
            # Validate required fields
            required_fields = [
                'total', 'shipping', 
                'first_name', 'last_name', 'email', 'phone_number',
                'product_id'  # Changed from item_id to product_id to match model
            ]
            
            for field in required_fields:
                if field not in data:
                    return Response(
                        {"error": f"Missing required field: {field}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            with transaction.atomic():
                # Create or update customer with all fields
                customer_data = {
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                    'phone_number': data['phone_number'],
                    'email': data['email'],
                    'additional_phone': data.get('additional_phone')
                }
                
                customer, created = Customers.objects.update_or_create(
                    phone_number=data['phone_number'],
                    defaults=customer_data
                )

                # Handle location creation
                if data.get('pickup_station_id'):
                    # Use existing pickup station
                    try:
                        location = Locations.objects.get(
                            id=data['pickup_station_id'],
                        )
                    except Locations.DoesNotExist:
                        return Response(
                            {"error": "Pickup station not found"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    # Create new delivery location
                    location_data = {
                        'street_address': data['street_address'],
                        'city': data['city'],
                        'state': data.get('state'),
                        'zip_code': data.get('zip_code'),
                        'name': data.get('location_name', 'Delivery Address'),
                        'description': data.get('location_description')
                    }
                    location = Locations.objects.create(**location_data)

                # Generate order number if not provided
                order_number = data.get('order_number') or f"ORD-{timezone.now().strftime('%Y%m%d%H%M%S')}"

                # Create order with all fields
                order_data = {
                    'order_number': order_number,
                    'total': Decimal(data['total']),
                    'shipping': Decimal(data['shipping']),
                    'status': data.get('status', 'pending'),
                    'delivery_option': 'pickup' if data.get('pickup_station_id') else 'delivery',
                    'notes': data.get('notes'),
                    'customer': customer,
                    'location': location
                }
                order = Order.objects.create(**order_data)

                # Add product to order
                try:
                    product = Product.objects.get(id=data['product_id'])
                    order.items.add(product)
                except Product.DoesNotExist:
                    return Response(
                        {"error": "Product not found"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Prepare complete response data
            response_data = {
                'order': {
                    'id': order.id,
                    'order_number': order.order_number,
                    'total': str(order.total),
                    'shipping': str(order.shipping),
                    'status': order.status,
                    'delivery_option': order.delivery_option,
                    'created': order.created,
                    'modified': order.modified
                },
                'customer': {
                    'id': customer.id,
                    'first_name': customer.first_name,
                    'last_name': customer.last_name,
                    'phone_number': customer.phone_number
                },
                'location': {
                    'id': location.id,
                    'name': location.name,
                    'type': location.type
                },
                'product': {
                    'id': product.id,
                    'name': product.name
                }
            }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating order: {str(e)}", exc_info=True)
            return Response(
                {"error": "Server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _serialize_product(self, product):
        """Helper method to serialize product data"""
        return {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'price': str(product.price),
            'description': product.description if product.description else None,
            'image_url': product.image_url if product.image_url else None,
            'created': product.created,
            'modified': product.modified
        }