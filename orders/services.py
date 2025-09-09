import datetime
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from django.db import transaction
from accounts.models import User, Address
from .models import Order,Warehouse, CartItems, OrderItem, Shipment, ShipmentItem, Coupon, CouponUsage
from decimal import Decimal
from collections import defaultdict
from returnrequest.models import transactions


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

def create_order_from_cart(user, cart, address_id, coupon_code, payment_method, is_paid=False):
    address = Address.objects.filter(user=user, id=address_id).first()
    cart_items = CartItems.objects.filter(CartID=cart)

    if not address:
        raise ValidationError("Address not found or does not belong to the user.")
    
    if not cart_items.exists():
        raise ValidationError("Cart is empty. Cannot create order.")

    # Replicate logic from OrderViewSet for total calculation and validations
    totals = _calculate_all_order_totals_helper(cart_items, coupon_code, address, user)

    with transaction.atomic():
        order = Order.objects.create(
            user=user,
            address=address,
            payment_method=payment_method,
            total_amount=totals['total_amount'],
            discount_amount=totals['discount_amount'],
            delivery_fee=totals['delivery_fee'],
            final_amount=totals['final_amount'],
            paid=is_paid
        )

        order_items_map = {}
        for item in cart_items:
            order_item = OrderItem.objects.create(
                order=order,
                product=item.Product,
                quantity=item.Quantity,
                price=item.Product.UnitPrice,
                color=item.Color,
                size=item.Size,
            )
            order_items_map[item.Product.id] = order_item

        items_by_supplier = defaultdict(list)
        for item in cart_items:
            items_by_supplier[item.Product.Supplier.user.id].append(item)
        supplier_addresses = _get_supplier_addresses_helper(cart_items, user)

        for supplier_id, items in items_by_supplier.items():
            supplier_address = supplier_addresses[supplier_id]
            supplier_state = supplier_address.State
            customer_state = address.State
            
            shipment_total = sum(item.Product.UnitPrice * item.Quantity for item in items)

            if supplier_state == customer_state:
                warehouse = get_warehouse_by_name(customer_state)
                _create_shipment_helper(
                    order, 
                    items[0].Product.Supplier,
                    supplier_addresses[supplier_id], 
                    address, 
                    items, 
                    Shipment.ShipmentStatus.CREATED,
                    warehouse.delivery_fee,
                    order_items_map,
                    shipment_total
                )
            else:
                warehouse_dest = get_warehouse_by_name(customer_state)
                warehouse_source = get_warehouse_by_name(supplier_state)
                
                _create_shipment_helper(
                    order, 
                    items[0].Product.Supplier,
                    warehouse_source.Address, 
                    address, 
                    items, 
                    Shipment.ShipmentStatus.In_Transmit,
                    warehouse_dest.delivery_fee,
                    order_items_map,
                    shipment_total
                )
                
                _create_shipment_helper(
                    order, 
                    items[0].Product.Supplier,
                    supplier_addresses[supplier_id], 
                    warehouse_dest.Address, 
                    items, 
                    Shipment.ShipmentStatus.CREATED,
                    warehouse_source.delivery_fee,
                    order_items_map,
                    shipment_total
                )
        
        _handle_payment_and_transactions_helper(user, payment_method, totals['final_amount'], is_paid)
        
        _update_product_stock_helper(cart_items)
        cart_items.delete()
        # _send_order_notification(user, order.id)

        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code)
                coupon.uses_count = F('uses_count') + 1
                coupon.save(update_fields=['uses_count'])
                
                CouponUsage.objects.create(user=user, coupon=coupon)
            except Coupon.DoesNotExist:
                pass

    return order

def _calculate_all_order_totals_helper(cart_items, coupon_code, customer_address, user):
    total_amount = Decimal('0.00')
    discount_amount = Decimal('0.00')
    delivery_fee = Decimal('0.00')

    items_by_supplier = defaultdict(list)
    for item in cart_items:
        items_by_supplier[item.Product.Supplier.user.id].append(item)
    
    supplier_addresses = _get_supplier_addresses_helper(cart_items, user)
    
    coupon = None
    if coupon_code:
        try:
            coupon = Coupon.objects.get(
                code=coupon_code,
                active=True,
                valid_from__lte=timezone.now(),
                valid_to__gte=timezone.now(),
            )
            
            if coupon.uses_count >= coupon.max_uses:
                 raise ValidationError({"message": "This coupon has exceeded its total usage limit."})
            
            user_uses_count = CouponUsage.objects.filter(user=user, coupon=coupon).count()
            if user_uses_count >= coupon.max_uses_per_user:
                raise ValidationError({"message": "Coupon usage limit reached for this user."})
            
        except Coupon.DoesNotExist:
            raise ValidationError({"message": "Invalid or expired coupon."})

    for supplier_id, items in items_by_supplier.items():
        shipment_total = sum(item.Product.UnitPrice * item.Quantity for item in items)
        shipment_discount = Decimal('0.00')

        if coupon and coupon.supplier.user.id == supplier_id:
            if shipment_total < coupon.min_purchase_amount:
                raise ValidationError({"message": f"Minimum purchase amount of {coupon.min_purchase_amount} not met for this coupon."})
                
            if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
                shipment_discount = (coupon.discount / Decimal('100.00')) * shipment_total
            elif coupon.discount_type == Coupon.DiscountType.FIXED_AMOUNT:
                shipment_discount = min(coupon.discount, shipment_total)

        current_delivery_fee = Decimal('0.00')
        supplier_address = supplier_addresses[supplier_id]
        customer_state = customer_address.State
        supplier_state = supplier_address.State
        
        if supplier_state == customer_state:
            warehouse = get_warehouse_by_name(customer_state)
            current_delivery_fee = warehouse.delivery_fee
        else:
            warehouse_dest = get_warehouse_by_name(customer_state)
            warehouse_source = get_warehouse_by_name(supplier_state)
            current_delivery_fee = warehouse_dest.delivery_fee + warehouse_source.delivery_fee + Decimal('20.00')
        
        total_amount += shipment_total
        discount_amount += shipment_discount
        delivery_fee += current_delivery_fee
    
    final_amount = total_amount - discount_amount + delivery_fee
    
    return {
        'total_amount': total_amount,
        'discount_amount': discount_amount,
        'delivery_fee': delivery_fee,
        'final_amount': final_amount
    }

def _create_shipment_helper(order, supplier, from_address, to_address, cart_items, status, delivery_fee, order_items_map, shipment_total):
    shipment = Shipment.objects.create(
        order=order,
        supplier=supplier,
        from_state=from_address.State,
        to_state=to_address.State,
        from_address=from_address,
        to_address=to_address,
        status=status,
        order_total_value=shipment_total
    )
    ShipmentItem.objects.bulk_create([
        ShipmentItem(
            shipment=shipment,
            order_item=order_items_map[item.Product.id],
            quantity=item.Quantity
        ) for item in cart_items
    ])
    return shipment

def _get_supplier_addresses_helper(cart_items, user):
    supplier_addresses = {}
    supplier_ids = {item.Product.Supplier.user.id for item in cart_items}
    for supplier_id in supplier_ids:
        addresses = Address.objects.filter(user=supplier_id)
        if not addresses.exists() or addresses.count() > 1:
            raise ValidationError({"message": f"Address not found or multiple addresses found for supplier with ID {supplier_id}."})
        supplier_addresses[supplier_id] = addresses.first()
    return supplier_addresses

def _handle_payment_and_transactions_helper(user, payment_method, final_amount, is_paid=False):
    Craft = get_craft_user_by_email("CraftEG@craft.com")
    if payment_method == Order.PaymentMethod.BALANCE:
        if user.Balance < final_amount:
            # This should have been validated in the view, so this is a safety check
            raise ValidationError({"message": "Insufficient balance for this order."})
        
        user.Balance -= final_amount
        Craft.Balance += final_amount
        transactions.objects.create(user=user, transaction_type=transactions.TransactionType.PURCHASED_PRODUCTS, amount=-final_amount)
        transactions.objects.create(user=Craft, transaction_type=transactions.TransactionType.PURCHASED_PRODUCTS, amount=final_amount)
        user.save()
    
    cashback_amount = final_amount * Decimal('0.05')
    user.Balance += cashback_amount    
    transactions.objects.create(user=user, transaction_type=transactions.TransactionType.CASH_BACK, amount=cashback_amount)
    
def _update_product_stock_helper(cart_items):
    for item in cart_items:
        item.Product.Stock = F('Stock') - item.Quantity
        item.Product.save(update_fields=['Stock'])