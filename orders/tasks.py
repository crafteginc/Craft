from celery import shared_task
from .services import (
    _process_payments,
    _update_product_stock,
    cancel_pending_credit_card_orders as cancel_pending_orders,
)
from .models import Order
from notifications.services import create_notification_for_user
from django.contrib.auth import get_user_model


@shared_task
def create_order_task(user_id, cart_id, address_id, coupon_code, payment_method, is_paid=False):
    """
    Asynchronous task to create an order.
    """
    from .services import create_order_from_cart
    from .models import Cart

    User = get_user_model()
    user = User.objects.get(id=user_id)
    cart = Cart.objects.get(id=cart_id)

    create_order_from_cart(user, cart, address_id, coupon_code, payment_method, is_paid)

@shared_task
def send_order_notification_task(user_id, message, order_id=None):
    """
    Asynchronous task to send a notification to a user.
    """
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        related_object = None
        if order_id:
            related_object = Order.objects.get(id=order_id)
        
        create_notification_for_user(
            user=user,
            message=message,
            related_object=related_object
        )
    except User.DoesNotExist:
        print(f"Could not send notification: User with id {user_id} not found.")
    except Order.DoesNotExist:
        print(f"Could not send notification: Order with id {order_id} not found for user {user_id}.")


@shared_task
def process_payments_task(user_id, shipment_id, warehouse_id):
    """
    Asynchronous task to process payments.
    """
    from .services import _process_payments
    from .models import Shipment, Warehouse
    from accounts.models import User

    user = User.objects.get(id=user_id)
    shipment = Shipment.objects.get(id=shipment_id)
    warehouse = Warehouse.objects.get(id=warehouse_id)
    _process_payments(user, shipment, warehouse)


@shared_task
def update_product_stock_task(cart_items):
    """
    Asynchronous task to update product stock.
    """
    from .services import _update_product_stock
    _update_product_stock(cart_items)


@shared_task
def cancel_pending_credit_card_orders_task():
    """
    Periodic task to cancel pending credit card orders.
    """
    cancel_pending_orders()