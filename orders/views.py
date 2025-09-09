from .models import CartItems, Cart, Order, OrderItem, Warehouse, Shipment, ShipmentItem, Coupon, CouponUsage
from .serializers import *
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.exceptions import ValidationError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from rest_framework import mixins, status, viewsets, generics
from rest_framework.permissions import IsAuthenticated
from accounts.models import Address, Delivery
from products.models import Product
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.decorators import action
from django.core.exceptions import ObjectDoesNotExist
from returnrequest.models import transactions
from .permissions import DeliveryContractProvided, IsSupplier
from .services import get_craft_user_by_email, get_warehouse_by_name, create_order_from_cart, _calculate_all_order_totals_helper
from decimal import Decimal
from collections import defaultdict
import datetime
from django.db.models import F

class WishlistViewSet(viewsets.ModelViewSet):
    queryset = Wishlist.objects.all()
    serializer_class = WishlistSerializer
    
    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        user = self.request.user
        existing_whishlist = Wishlist.objects.filter(user=user).first()
        if existing_whishlist:
            raise ValidationError("A whishlist already exists for this user")
        serializer.save(user=user)
        return Response({"message": "whishlist created successfully"}, status=status.HTTP_201_CREATED)
    
class WishlistItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = WishlistItem.objects.all()
    serializer_class = WishlistItemSerializer

    def get_queryset(self):
        user = self.request.user
        return WishlistItem.objects.filter(wishlist__user=user)

    def get_serializer_class(self):
        if self.action == "create":
            return AddWishlistItemSerializer
        return WishlistItemSerializer

    def perform_create(self, serializer):
        user = self.request.user
        wishlist, created = Wishlist.objects.get_or_create(user=user)
        serializer.save(wishlist=wishlist)

class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    
    def get_queryset(self):
        return Cart.objects.filter(User=self.request.user)
    
    def perform_create(self, serializer):
        user = self.request.user
        existing_cart = Cart.objects.filter(User=user).first()
        if existing_cart:
            raise ValidationError("A cart already exists for this user")
        serializer.save(User=user)
        return Response({"message": "Cart created successfully"}, status=status.HTTP_201_CREATED)
    
class CartItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = CartItems.objects.all()
    serializer_class = CartItemSerializer

    def get_queryset(self):
        user = self.request.user
        return CartItems.objects.filter(CartID__User=user)

    def get_serializer_class(self):
        if self.action == "create":
            return AddCartItemSerializer
        elif self.action == "update":
            return UpdateCartItemSerializer
        return CartItemSerializer

    def perform_create(self, serializer):
        user = self.request.user
        cart, created = Cart.objects.get_or_create(User=user)
        serializer.save(CartID=cart)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.CartID.User != request.user:
            return Response(
                {"message": "You cannot delete items from another user's cart."},
                status=status.HTTP_403_FORBIDDEN,
            )
        self.perform_destroy(instance)
        return Response(
            {"message": "Cart item deleted successfully."},
            status=status.HTTP_200_OK,  
        )

Craft = get_craft_user_by_email("CraftEG@craft.com")
if Craft:
    print("User found:", Craft)
else:
    print("User not found.")
 
class OrderViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = OrderCreateSerializer
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            if hasattr(user, 'delivery'):
                return Order.objects.for_delivery_person(user)
            return Order.objects.for_customer(user)
        return Order.objects.none()

    @action(detail=False, methods=['post'], url_path='calculate-totals')
    def calculate_totals(self, request, *args, **kwargs):
        cart = Cart.objects.get(User=request.user)
        address_id = request.data.get("address_id")
        coupon_code = request.data.get("coupon_code")
        
        payment_method = ""
        self._validate_request_data(cart, address_id, payment_method)
        address = Address.objects.filter(user=request.user, id=address_id).first()
        if not address:
            raise ValidationError("Address not found or does not belong to the user.")

        cart_items = CartItems.objects.filter(CartID=cart)
        self._validate_cart_stock(cart_items)

        totals = _calculate_all_order_totals_helper(cart_items, coupon_code, address, request.user)

        return Response({
            "message": "Order totals calculated successfully",
            "Total amount": totals['total_amount'],
            "Discount amount": totals['discount_amount'],
            "Deliverey Fee": totals['delivery_fee'],
            "final_amount": totals['final_amount']
        }, status=status.HTTP_200_OK)
    
    def create(self, request, *args, **kwargs):
        cart = Cart.objects.get(User=request.user)
        address_id = request.data.get("address_id")
        coupon_code = request.data.get("coupon_code")
        payment_method = request.data.get("payment_method", "").strip()

        self._validate_request_data(cart, address_id, payment_method)
        address = Address.objects.filter(user=request.user, id=address_id).first()
        cart_items = CartItems.objects.filter(CartID=cart)
        
        self._validate_cart_stock(cart_items)

        if payment_method == Order.PaymentMethod.CREDIT_CARD:
            return Response({
                "message": "Redirecting to payment gateway...",
                "status": "pending_payment"
            }, status=status.HTTP_200_OK)
        
        if payment_method == Order.PaymentMethod.BALANCE:
            totals = _calculate_all_order_totals_helper(cart_items, coupon_code, address, request.user)
            if request.user.Balance < totals['final_amount']:
                raise ValidationError({"message": "Insufficient balance for this order."})
        
        order = create_order_from_cart(request.user, cart, address_id, coupon_code, payment_method)
        
        return Response({
            "message": "Order Created Successfully",
            "order_id": str(order.id),
            "Total amount": order.total_amount,
            "Discount amount": order.discount_amount,
            "Deliverey Fee": order.delivery_fee,
            "final_amount": order.final_amount
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='orders-for-me', permission_classes=[IsAuthenticated, IsSupplier])
    def orders_for_me(self, request):
        """
        Retrieves a simplified list of orders for the current supplier.
        """
        user = request.user
        queryset = Order.objects.filter(items__product__Supplier=user.supplier).distinct().order_by('-created_at')
        serializer = SupplierOrderListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'], url_path='orders-for-me-details', permission_classes=[IsAuthenticated, IsSupplier])
    def retrieve_supplier_order(self, request, pk=None):

        user = request.user
        try:
            order = Order.objects.get(pk=pk, items__product__Supplier=user.supplier)
        except Order.DoesNotExist:
            return Response({"message": "Order not found or you don't have permission to view it."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = SupplierOrderRetrieveSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='ready-to-ship', permission_classes=[IsAuthenticated, IsSupplier])
    def ready_to_ship(self, request, pk=None):
        """
        Allows a supplier to mark a shipment as "ready to ship."
        """
        user = request.user
        try:
            shipment = Shipment.objects.get(
                order__pk=pk, 
                supplier=user.supplier,
                status=Shipment.ShipmentStatus.CREATED
            )
        except Shipment.DoesNotExist:
            return Response({"message": "Shipment not found or is not in a 'created' state."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            shipment.status = Shipment.ShipmentStatus.READY_TO_SHIP
            shipment.save()
            shipment.order.status = Order.OrderStatus.READY_TO_SHIP
            shipment.order.save()
        
        return Response({"message": f"Shipment for order {pk} is now ready to ship."}, status=status.HTTP_200_OK)

    def _validate_request_data(self, cart, address_id, payment_method):
        if not address_id:
            raise ValidationError({"message": "Address ID is required."})
        if cart.items.count() == 0:
            raise ValidationError({"message": "Cart is empty. Cannot create order."})
        if payment_method and payment_method not in Order.PaymentMethod.values:
            raise ValidationError({"message": "Invalid or missing payment method."})

    def _validate_cart_stock(self, cart_items):
        for item in cart_items:
            if item.Quantity > item.Product.Stock:
                raise ValidationError({"message": f"Quantity of {item.Product.ProductName} exceeds available stock."})
    
    def _get_supplier_addresses(self, cart_items):
        supplier_addresses = {}
        supplier_ids = {item.Product.Supplier.user.id for item in cart_items}
        for supplier_id in supplier_ids:
            addresses = Address.objects.filter(user=supplier_id)
            if not addresses.exists() or addresses.count() > 1:
                raise ValidationError({"message": f"Address not found or multiple addresses found for supplier with ID {supplier_id}."})
            supplier_addresses[supplier_id] = addresses.first()
        return supplier_addresses

    def _update_product_stock(self, cart_items):
        for item in cart_items:
            item.Product.Stock = F('Stock') - item.Quantity
            item.Product.save(update_fields=['Stock'])

    def _send_order_notification(self, user, order_id):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "send_notification",
                "message": f"Your order with ID {order_id} has been created."
            }
        )

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return OrderListRetrieveSerializer
        return self.serializer_class
    
    @action(detail=True, methods=['post'], url_path='cancel', url_name='cancel-order')
    def cancel_order(self, request, pk=None):
        try:
            user = request.user
            order = Order.objects.get(pk=pk, user=user)
            
            if order.user != request.user:
                return Response({"message": "You do not have permission to cancel this order."}, status=status.HTTP_403_FORBIDDEN)
        
            if order.status in [Order.OrderStatus.CREATED, Order.OrderStatus.In_Transmit]:
                with transaction.atomic():
                    order.status = Order.OrderStatus.CANCELLED
                    order.save()
                    
                    cashback_amount = order.final_amount * Decimal('0.05')
                    
                    if order.payment_method == Order.PaymentMethod.BALANCE:
                        user.Balance += order.final_amount
                        user.Balance -= cashback_amount
                        transactions.objects.create(user=user, transaction_type=transactions.TransactionType.CASH_BACK, amount=-cashback_amount)
                        transactions.objects.create(user=user, transaction_type=transactions.TransactionType.RETURNED_PRODUCT, amount=order.final_amount)
                    elif order.payment_method == Order.PaymentMethod.CREDIT_CARD and order.paid:
                        user.Balance += order.final_amount
                        user.Balance -= cashback_amount
                        transactions.objects.create(user=user, transaction_type=transactions.TransactionType.RETURNED_CASH_BACK, amount=-cashback_amount)
                        transactions.objects.create(user=user, transaction_type=transactions.TransactionType.RETURNED_PRODUCT, amount=order.final_amount)
                    elif order.payment_method == Order.PaymentMethod.CASH_ON_DELIVERY:
                        user.Balance -= cashback_amount
                        transactions.objects.create(user=user, transaction_type=transactions.TransactionType.RETURNED_CASH_BACK, amount=-cashback_amount)
                
                return Response({"message": "Order has been cancelled."}, status=status.HTTP_200_OK)
            else:
                return Response({"message": "Cannot cancel an order that has been delivered or marked as failed delivery."}, status=status.HTTP_400_BAD_REQUEST)
        
        except Order.DoesNotExist:
            return Response({"message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

class ShipmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ShipmentSerializer
    permission_classes = [IsAuthenticated, DeliveryContractProvided]
    queryset = Shipment.objects.all()

    def get_queryset(self):
        user = self.request.user
        if not hasattr(user, 'delivery'):
            return Shipment.objects.none()

        return Shipment.objects.filter(
            Q(status=Shipment.ShipmentStatus.READY_TO_SHIP) & Q(to_state=user.delivery.governorate) |
            Q(status=Shipment.ShipmentStatus.DELIVERED_TO_Second_WAREHOUSE) & Q(to_state=user.delivery.governorate) |
            Q(delivery_person=user.delivery) & Q(status=Shipment.ShipmentStatus.ON_MY_WAY)
        ).order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='accept')
    def accept(self, request, pk=None):
        try:
            shipment = self.get_queryset().get(pk=pk, delivery_person=None)
        except Shipment.DoesNotExist:
            return Response({'message': 'Shipment not found or is already taken.'}, status=status.HTTP_404_NOT_FOUND)
        
        with transaction.atomic():
            shipment.delivery_person = request.user.delivery
            shipment.status = Shipment.ShipmentStatus.ON_MY_WAY
            shipment.save()
            
            order = shipment.order
            if not order.shipments.exclude(status=Shipment.ShipmentStatus.ON_MY_WAY).exists():
                order.status = Order.OrderStatus.ON_MY_WAY
                order.save()

        return Response({'status': 'Shipment accepted and status updated to on my way'})

    @action(detail=True, methods=['post'], url_path='delivered')
    def delivered(self, request, pk=None):
        try:
            shipment = self.get_queryset().get(pk=pk, delivery_person=request.user.delivery)
        except Shipment.DoesNotExist:
            return Response({'message': 'Shipment not found or you are not assigned to it.'}, status=status.HTTP_404_NOT_FOUND)

        confirmation_code = request.data.get('confirmation_code')
        if confirmation_code != shipment.confirmation_code:
            return Response({"message": "Invalid confirmation code."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            warehouse = get_warehouse_by_name(shipment.to_state)
            
            shipment.status = Shipment.ShipmentStatus.DELIVERED_SUCCESSFULLY
            shipment.delivery_confirmed_at = timezone.now()
            shipment.save()
            
            order = shipment.order
            if all(s.status == Shipment.ShipmentStatus.DELIVERED_SUCCESSFULLY for s in order.shipments.all()):
                order.status = Order.OrderStatus.DELIVERED_SUCCESSFULLY
                order.save()
            
            self._process_payments(request.user, shipment, warehouse)
        
        return Response({'message': 'Shipment status updated to delivered successfully'}, status=status.HTTP_200_OK)

    def _process_payments(self, user, shipment, warehouse):
        Craft = get_craft_user_by_email("CraftEG@craft.com")
        delivery_fee_share = warehouse.delivery_fee * Decimal('0.85')
        craft_delivery_cut = warehouse.delivery_fee * Decimal('0.15')
        
        order_items = shipment.items.all()
        supplier_total = sum(item.order_item.price * item.order_item.quantity for item in order_items)
        
        supplier_revenue = supplier_total * Decimal('0.85')
        craft_supplier_cut = supplier_total * Decimal('0.15')

        if shipment.order.payment_method in [Order.PaymentMethod.BALANCE, Order.PaymentMethod.CREDIT_CARD]:
            user.Balance += delivery_fee_share
            Craft.Balance += craft_delivery_cut
            transactions.objects.create(user=user, transaction_type=transactions.TransactionType.DELIVERY_FEE, amount=delivery_fee_share)
            transactions.objects.create(user=Craft, transaction_type=transactions.TransactionType.DELIVERY_FEE, amount=craft_delivery_cut)

            shipment.supplier.user.Balance += supplier_revenue
            Craft.Balance += craft_supplier_cut
            transactions.objects.create(user=shipment.supplier.user, transaction_type=transactions.TransactionType.PURCHASED_PRODUCTS, amount=supplier_revenue)
            transactions.objects.create(user=Craft, transaction_type=transactions.TransactionType.SUPPLIER_TRANSFORM, amount=craft_supplier_cut)
                
        elif shipment.order.payment_method == Order.PaymentMethod.CASH_ON_DELIVERY:
            user.Balance -= (supplier_total + warehouse.delivery_fee)
            shipment.supplier.user.Balance += supplier_revenue
            Craft.Balance += craft_supplier_cut + craft_delivery_cut
            
            transactions.objects.create(user=user, transaction_type=transactions.TransactionType.DELIVERY_FEE, amount=-(supplier_total + warehouse.delivery_fee))
            transactions.objects.create(user=shipment.supplier.user, transaction_type=transactions.TransactionType.PURCHASED_PRODUCTS, amount=supplier_revenue)
            transactions.objects.create(user=Craft, transaction_type=transactions.TransactionType.SUPPLIER_TRANSFORM, amount=craft_supplier_cut)
            transactions.objects.create(user=Craft, transaction_type=transactions.TransactionType.DELIVERY_FEE, amount=craft_delivery_cut)

class OrdersHistoryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = OrderListRetrieveSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return Order.objects.filter(user=user).order_by('-created_at')
        return Order.objects.none()

class ReturnOrdersProductsViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ReturnRequestListRetrieveSerializer  
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        fourteen_days_ago = timezone.now() - datetime.timedelta(days=14)
        if user.is_customer:
            return Order.objects.filter(user=user, updated_at__gte=fourteen_days_ago)
        return Order.objects.none()

class CouponViewSet(viewsets.ModelViewSet):
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_supplier:
            return Coupon.objects.filter(supplier=self.request.user.supplier)
        return Coupon.objects.filter(active=True)

    def perform_create(self, serializer):
        coupon = serializer.save(supplier=self.request.user.supplier)
        supplier_products = Product.objects.filter(Supplier=self.request.user.supplier)
        coupon.products.set(supplier_products)
    
    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.supplier != self.request.user.supplier:
            return Response({"message": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)
        serializer.save()
        supplier_products = Product.objects.filter(Supplier=self.request.user.supplier)
        instance.products.set(supplier_products)

    def perform_destroy(self, instance):
        if instance.supplier != self.request.user.supplier:
            return Response({"message": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)
        instance.delete()
        return Response({"message": "Coupon deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

class WarehouseListView(generics.ListAPIView):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer