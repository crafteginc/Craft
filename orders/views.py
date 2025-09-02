from .models import CartItems,Cart, Order, OrderItem,Warehouse,Shipment,DeliveryOrder
from .serializers import *
from rest_framework.response import Response
from rest_framework import status ,permissions
from rest_framework.exceptions import ValidationError
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from rest_framework import mixins, status, viewsets ,generics
from rest_framework.permissions import IsAuthenticated
from accounts.models import Address
from django.db.models import F
from django.utils import timezone
from rest_framework.decorators import action
from accounts.models import Delivery
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from returnrequest.models import transactions
from .permissions import DeliveryContractProvided
from .Help import get_craft_user_by_email , get_warehouse_by_name
from decimal import Decimal
from collections import defaultdict

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
        data=serializer.save(user=user)
        return Response({"message": "whishlist created successfully"}, status=status.HTTP_201_CREATED)
    
class WishlistItemViewSet(viewsets.ModelViewSet):
    permission_classes= [permissions.IsAuthenticated]
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
    permission_classes= [permissions.IsAuthenticated]
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
            if user.is_delivery:
                return Order.objects.for_delivery_person(user)
            return Order.objects.for_customer(user)
        return Order.objects.none()

    @action(detail=False, methods=['post'], url_path='calculate-totals')
    def calculate_totals(self, request, *args, **kwargs):
        """
        Calculates and returns the order totals without creating an order.
        """
        cart = Cart.objects.get(User=request.user)
        address_id = request.data.get("address_id")
        coupon_code = request.data.get("coupon_code")
        
        # The payment method is not required for calculation, but address_id is.
        # We also need a placeholder for the validation function.
        payment_method = ""
        self._validate_request_data(cart, address_id, payment_method)
        address = Address.objects.filter(user=request.user, id=address_id).first()
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
            
            # Create the main order instance
            order = Order.objects.create(
                user=request.user,
                address=address,
                payment_method=payment_method,
                total_amount=totals['total_amount'],
                discount_amount=totals['discount_amount'],
                delivery_fee=totals['delivery_fee'],
                final_amount=totals['final_amount']
            )

            # Re-group items by supplier to create shipments
            items_by_supplier = defaultdict(list)
            for item in cart_items:
                items_by_supplier[item.Product.Supplier.user.id].append(item)
            supplier_addresses = self._get_supplier_addresses(cart_items)

            for supplier_id, items in items_by_supplier.items():
                supplier_address = supplier_addresses[supplier_id]
                supplier_state = supplier_address.State
                customer_state = address.State
                
                # Check for single-state shipment
                if supplier_state == customer_state:
                    warehouse = get_warehouse_by_name(customer_state)
                    current_delivery_fee = warehouse.delivery_fee
                    self._create_shipment(
                        order, 
                        supplier_addresses[supplier_id], 
                        address, 
                        items, 
                        Shipment.ShipmentStatus.CREATED,
                        current_delivery_fee
                    )
                # Check for multi-state shipment
                else:
                    warehouse_dest = get_warehouse_by_name(customer_state)
                    warehouse_source = get_warehouse_by_name(supplier_state)
                    
                    # Create the In_Transmit shipment to the destination warehouse
                    current_delivery_fee = warehouse_dest.delivery_fee
                    self._create_shipment(
                        order, 
                        warehouse_source.Address, 
                        address, 
                        items, 
                        Shipment.ShipmentStatus.In_Transmit,
                        current_delivery_fee
                    )
                    
                    # Create the final delivery shipment from the source warehouse to the customer
                    current_delivery_fee = warehouse_source.delivery_fee + Decimal('20.00')
                    self._create_shipment(
                        order, 
                        supplier_addresses[supplier_id], 
                        warehouse_dest.Address, 
                        items, 
                        Shipment.ShipmentStatus.CREATED,
                        current_delivery_fee,
                    )
            
            # Handle payment logic for the total order amount
            self._handle_payment_and_transactions(request.user, payment_method, totals['final_amount'], totals['delivery_fee'])
            
            self._update_product_stock(cart_items)
            cart_items.delete()
            self._send_order_notification(request.user, order.id)

        # Return the desired final response format
        return Response({
            "message": "Order Created Successfully",
            "order_id": str(order.id),
            "Total amount": order.total_amount,
            "Discount amount": order.discount_amount,
            "Deliverey Fee": order.delivery_fee,
            "final_amount": order.final_amount
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='orders-for-me')
    def orders_for_me(self, request):
        """
        Retrieves orders placed by other customers and suppliers for the current supplier's products.
        """
        user = request.user
        if not user.is_supplier:
            return Response({"message": "You must be a supplier to view this data."}, status=status.HTTP_403_FORBIDDEN)
        
        queryset = Order.objects.filter(shipments__supplier=user.supplier).distinct()
        serializer = OrderListRetrieveSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _calculate_all_order_totals(self, cart_items, coupon_code, customer_address):
        """
        Helper method to calculate all order totals based on cart items and customer address.
        This method does not create any database records.
        """
        total_amount = Decimal('0.00')
        discount_amount = Decimal('0.00')
        delivery_fee = Decimal('0.00')

        items_by_supplier = defaultdict(list)
        for item in cart_items:
            items_by_supplier[item.Product.Supplier.user.id].append(item)
        
        supplier_addresses = self._get_supplier_addresses(cart_items)

        for supplier_id, items in items_by_supplier.items():
            supplier_address = supplier_addresses[supplier_id]
            supplier_state = supplier_address.State
            customer_state = customer_address.State
            
            shipment_total, shipment_discount = self._calculate_shipment_totals(items, coupon_code)
            
            current_delivery_fee = Decimal('0.00')
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

    def _create_shipment(self, order, from_address, to_address, cart_items, status, delivery_fee):
        shipment = Shipment.objects.create(
            order=order,
            supplier=cart_items[0].Product.Supplier,
            from_state=from_address.State,
            to_state=to_address.State,
            from_address=from_address,
            to_address=to_address,
            status=status,
        )
        # Link order items to the new shipment
        OrderItem.objects.bulk_create([
            OrderItem(
                shipment=shipment,
                product=item.Product,
                quantity=item.Quantity,
                price=item.Product.UnitPrice,
                color=item.Color,
                size=item.Size,
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
        # The payment_method is not a required field for `calculate_totals`, so no further validation is needed.

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

    def _calculate_shipment_totals(self, cart_items, coupon_code):
        total_amount = sum(item.Product.UnitPrice * item.Quantity for item in cart_items)
        discount_amount = Decimal('0.00')
        if coupon_code:
            try:
                coupon = Coupon.objects.get(
                    code=coupon_code,
                    active=True,
                    valid_from__lte=timezone.now(),
                    valid_to__gte=timezone.now()
                )
                if any(item.Product.Supplier == coupon.supplier for item in cart_items):
                    discount_amount = (coupon.discount / Decimal('100.00')) * total_amount
            except Coupon.DoesNotExist:
                raise ValidationError({"message": "Invalid or expired coupon."})
        return total_amount, discount_amount

    def _handle_payment_and_transactions(self, user, payment_method, final_amount, delivery_fee):
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
            item.Product.save() 

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
    
    @action(detail=True, methods=['post'], url_path='accept', permission_classes=[IsAuthenticated, DeliveryContractProvided])
    def accept(self, request, pk=None):
        order = self.get_object()
        user = request.user
        
        if not user.is_delivery:
            return Response({'message': 'You are not authorized to accept orders.'}, status=status.HTTP_403_FORBIDDEN)
        
        if hasattr(order, 'delivery_order') and order.delivery_order.delivery_person != user:
            return Response({'message': 'This order has already been accepted by another delivery person.'}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            delivery_order, created = DeliveryOrder.objects.get_or_create(order=order, defaults={'delivery_person': user})
            if not created and delivery_order.delivery_person != user:
                return Response({'message': 'This order has already been accepted by another delivery person.'}, status=status.HTTP_400_BAD_REQUEST)
            
            order.status = Order.OrderStatus.ON_MY_WAY
            order.delivery = user.delivery
            order.save()
        
        return Response({'status': 'Order accepted and status updated to on my way'})
    
    @action(detail=True, methods=['post'], url_path='delivered')
    def delivered(self, request, pk=None):
        try:
            user = request.user
            order = Order.objects.get(pk=pk, delivery=user.delivery)
            
            if not user.is_delivery:
                return Response({"message": "Only delivery persons can mark orders as delivered."}, status=status.HTTP_403_FORBIDDEN)
            
            try:
                DeliveryOrder.objects.get(order=order, delivery_person=user)
            except DeliveryOrder.DoesNotExist:
                return Response({"message": "This order is not accepted by you."}, status=status.HTTP_403_FORBIDDEN)
            
            serializer = OrderDeliverSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            confirmation_code = serializer.validated_data.get('confirmation_code')
            if confirmation_code != order.confirmation_code:
                return Response({"message": "Invalid confirmation code."}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                warehouse = get_warehouse_by_name(user.delivery.governorate)
                if order.related_order:
                    order.status = Order.OrderStatus.DELIVERED_SUCCESSFULLY
                    order.delivery_confirmed_at = timezone.now()
                    self._process_payments(user, order, warehouse, True)
                else:
                    order.status = Order.OrderStatus.DELIVERED_SUCCESSFULLY
                    order.delivery_confirmed_at = timezone.now()
                    self._process_payments(user, order, warehouse, False)
                order.save()
            
            return Response({'message': 'Order status updated to delivered successfully'}, status=status.HTTP_200_OK)
        
        except Order.DoesNotExist:
            return Response({"message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

    def _process_payments(self, user, order, warehouse, has_related_order):
        # Delivery person and Craft's cut
        delivery_fee_share = warehouse.delivery_fee * Decimal('0.85')
        craft_delivery_cut = warehouse.delivery_fee * Decimal('0.15')
        
        # Supplier and Craft's cut
        supplier_revenue = order.total_amount * Decimal('0.85')
        craft_supplier_cut = order.total_amount * Decimal('0.15')

        if order.payment_method in [Order.PaymentMethod.BALANCE, Order.PaymentMethod.CREDIT_CARD]:
            # Cashless payments
            user.Balance += delivery_fee_share
            Craft.Balance += craft_delivery_cut
            transactions.objects.create(user=user, transaction_type=transactions.TransactionType.DELIVERY_FEE, amount=delivery_fee_share)
            transactions.objects.create(user=Craft, transaction_type=transactions.TransactionType.DELIVERY_FEE, amount=craft_delivery_cut)

            if not has_related_order:
                order.supplier.user.Balance += supplier_revenue
                Craft.Balance += craft_supplier_cut
                transactions.objects.create(user=order.supplier.user, transaction_type=transactions.TransactionType.PURCHASED_PRODUCTS, amount=supplier_revenue)
                transactions.objects.create(user=Craft, transaction_type=transactions.TransactionType.SUPPLIER_TRANSFORM, amount=craft_supplier_cut)
                
        elif order.payment_method == Order.PaymentMethod.CASH_ON_DELIVERY:
            # Cash payments: Delivery person owes Craft money
            delivery_final_amount = order.final_amount - warehouse.delivery_fee
            user.Balance -= delivery_final_amount
            order.supplier.user.Balance += supplier_revenue
            Craft.Balance += craft_supplier_cut
            
            transactions.objects.create(user=user, transaction_type=transactions.TransactionType.DELIVERY_FEE, amount=-delivery_final_amount)
            transactions.objects.create(user=order.supplier.user, transaction_type=transactions.TransactionType.PURCHASED_PRODUCTS, amount=supplier_revenue)
            transactions.objects.create(user=Craft, transaction_type=transactions.TransactionType.DELIVERY_FEE, amount=craft_supplier_cut)
            
            if not has_related_order:
                pass

    @action(detail=False, methods=['get'], url_path='accepted_orders')
    def accepted_orders(self, request):
        try:
            # Ensure the user is a delivery person and access the related Delivery profile
            delivery_person = request.user
            delivery_profile = delivery_person.delivery
            # Filter orders accepted by the current delivery person
            orders = Order.objects.filter(
                delivery_orders__delivery_person=delivery_person,
                status=Order.OrderStatus.ON_MY_WAY
            )
            serializer = self.get_serializer(orders, many=True)
            return Response(serializer.data)
        except Delivery.DoesNotExist:
            return Response({"message": "Delivery profile does not exist."}, status=status.HTTP_400_BAD_REQUEST)
        except AttributeError:
            return Response({"message": "User does not have a delivery profile."}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=True, methods=['post'], url_path='cancel', url_name='cancel-order')
    def cancel_order(self, request, pk=None):
        try:
            user = request.user
            order = Order.objects.get(pk=pk, user=user)
            
            if order.user != request.user:
                return Response({"message": "You do not have permission to cancel this order."}, status=status.HTTP_403_FORBIDDEN)
        
            if order.status in [Order.OrderStatus.CREATED ,Order.OrderStatus.PAID,Order.OrderStatus.In_Transmit] :
                with transaction.atomic():
                    order.status = Order.OrderStatus.CANCELLED
                    order.save()
                    if order.related_order:
                        related_order = order.related_order
                        related_order.status = Order.OrderStatus.CANCELLED
                        related_order.save()
                    
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

class OrdersHistoryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = OrderListRetrieveSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            # Returns orders placed by the user, regardless of their role
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
