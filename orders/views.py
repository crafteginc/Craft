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
from .services import get_craft_user_by_email, get_warehouse_by_name
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

        totals = self._calculate_all_order_totals(cart_items, coupon_code, address)

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

        with transaction.atomic():
            totals = self._calculate_all_order_totals(cart_items, coupon_code, address)
            
            order = Order.objects.create(
                user=request.user,
                address=address,
                payment_method=payment_method,
                total_amount=totals['total_amount'],
                discount_amount=totals['discount_amount'],
                delivery_fee=totals['delivery_fee'],
                final_amount=totals['final_amount']
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
            supplier_addresses = self._get_supplier_addresses(cart_items)

            for supplier_id, items in items_by_supplier.items():
                supplier_address = supplier_addresses[supplier_id]
                supplier_state = supplier_address.State
                customer_state = address.State
                
                shipment_total = sum(item.Product.UnitPrice * item.Quantity for item in items)

                if supplier_state == customer_state:
                    warehouse = get_warehouse_by_name(customer_state)
                    self._create_shipment(
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
                    
                    self._create_shipment(
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
                    
                    self._create_shipment(
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
            
            self._handle_payment_and_transactions(request.user, payment_method, totals['final_amount'])
            
            self._update_product_stock(cart_items)
            cart_items.delete()
            self._send_order_notification(request.user, order.id)
            
            if coupon_code:
                try:
                    coupon = Coupon.objects.get(code=coupon_code)
                    coupon.uses_count = F('uses_count') + 1
                    coupon.save(update_fields=['uses_count'])
                    
                    # Create a record for the user's usage
                    CouponUsage.objects.create(user=request.user, coupon=coupon)
                except Coupon.DoesNotExist:
                    pass

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

    def _calculate_all_order_totals(self, cart_items, coupon_code, customer_address):
        total_amount = Decimal('0.00')
        discount_amount = Decimal('0.00')
        delivery_fee = Decimal('0.00')

        items_by_supplier = defaultdict(list)
        for item in cart_items:
            items_by_supplier[item.Product.Supplier.user.id].append(item)
        
        supplier_addresses = self._get_supplier_addresses(cart_items)
        
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
                
                user_uses_count = CouponUsage.objects.filter(user=self.request.user, coupon=coupon).count()
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

    def _create_shipment(self, order, supplier, from_address, to_address, cart_items, status, delivery_fee, order_items_map, shipment_total):
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
    
    def _handle_payment_and_transactions(self, user, payment_method, final_amount):
        if payment_method == Order.PaymentMethod.BALANCE:
            if user.Balance < final_amount:
                raise ValidationError({"message": "Insufficient balance for this order. Your Payment Method will turn into Cash on Delivery."})
            
            user.Balance -= final_amount
            Craft.Balance += final_amount
            transactions.objects.create(user=user, transaction_type=transactions.TransactionType.PURCHASED_PRODUCTS, amount=-final_amount)
            transactions.objects.create(user=Craft, transaction_type=transactions.TransactionType.PURCHASED_PRODUCTS, amount=final_amount)
            user.save()
            
        cashback_amount = final_amount * Decimal('0.05')
        transactions.objects.create(user=user, transaction_type=transactions.TransactionType.CASH_BACK, amount=cashback_amount)

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
        fourteen_days_ago = timezone.now() - timezone.timedelta(days=14)
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