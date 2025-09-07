import datetime
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from django.db import transaction
from accounts.models import User
from .models import Order,Warehouse

def get_craft_user_by_email(email="CraftEG@craft.com"):
    try:
        return User.objects.get(email=email)
    except User.DoesNotExist:
        return None
    except Exception as e:
        print(f"Error occurred: {e}")
        return None

def get_warehouse_by_name(state_name):
    try:
        return Warehouse.objects.get(name=state_name)
    except Warehouse.DoesNotExist:
        raise ValidationError(f"Warehouse not found for state: {state_name}")

def cancel_order_and_restock(order):
    """
    Cancels an order, sets its status, and restocks the associated products.
    """
    if order.paid:
        raise ValidationError("Cannot cancel an order that has already been paid.")

    with transaction.atomic():
        order.status = Order.OrderStatus.CANCELLED
        order.paid = False
        order.save()

        # Restore product stock for all items in the order
        for order_item in order.items.all():
            product = order_item.product
            product.Stock = F('Stock') + order_item.quantity
            product.save()

        # You would also handle other related entities here, like removing shipments, etc.
        # For example: order.shipments.all().delete()
    
def cancel_pending_credit_card_orders():
    """
    Background task to find and cancel unpaid credit card orders older than 24 hours.
    This should be run periodically (e.g., daily) using a scheduler like Celery.
    """
    time_threshold = timezone.now() - datetime.timedelta(hours=24)
    pending_orders = Order.objects.filter(
        payment_method=Order.PaymentMethod.CREDIT_CARD,
        paid=False,
        status=Order.OrderStatus.CREATED,
        created_at__lte=time_threshold
    )

    for order in pending_orders:
        try:
            cancel_order_and_restock(order)
            print(f"Successfully cancelled expired order {order.id}")
        except Exception as e:
            print(f"Failed to cancel order {order.id}: {e}")