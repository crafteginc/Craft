import datetime
from decimal import Decimal

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Address
from notifications.services import create_notification_for_user
from products.models import Product
from products.views import StandardResultsSetPagination
from returnrequest.models import Transaction

from .models import Cart, CartItems, Coupon, Order, Shipment, Warehouse, Wishlist, WishlistItem
from .permissions import DeliveryContractProvided, IsSupplier
from .serializers import (
    AddCartItemSerializer, AddWishlistItemSerializer, CartItemSerializer,
    CartSerializer, CouponSerializer, OrderCreateSerializer,
    OrderRetrieveSerializer, OrderSimpleListSerializer,
    ReturnRequestListRetrieveSerializer, ShipmentSerializer,
    SupplierOrderRetrieveSerializer, UpdateCartItemSerializer,
    WarehouseSerializer, WishlistItemSerializer, WishlistSerializer
)
from .services import (
    _calculate_all_order_totals_helper, _validate_cart_stock,
    _validate_request_data, get_craft_user_by_email, get_warehouse_by_name
)
from .tasks import (
    create_order_task, process_payments_task, send_order_notification_task
)


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
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            if hasattr(user, 'delivery'):
                return Order.objects.for_delivery_person(user)
            return Order.objects.for_customer(user)
        return Order.objects.none()

    def get_serializer_class(self):
        if self.action in ["list", "list_completed_supplier_orders", "list_uncompleted_supplier_orders"]:
            return OrderSimpleListSerializer
        if self.action == "retrieve":
            return OrderRetrieveSerializer
        if self.action == "retrieve_supplier_order":
            return SupplierOrderRetrieveSerializer
        if self.action in ["for_supplier", "for_supplier_as_customer"]:
            return OrderSimpleListSerializer
        return OrderCreateSerializer

    @action(detail=False, methods=['get'], url_path='completed-supplier-orders',
            permission_classes=[IsAuthenticated, IsSupplier])
    def list_completed_supplier_orders(self, request):
        user = self.request.user
        queryset = Order.objects.for_supplier(user).exclude(
            shipments__status=Shipment.ShipmentStatus.CREATED
        ).distinct().order_by('-created_at')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='uncompleted-supplier-orders',
            permission_classes=[IsAuthenticated, IsSupplier])
    def list_uncompleted_supplier_orders(self, request):
        queryset = Order.objects.for_supplier(request.user).filter(
            shipments__status=Shipment.ShipmentStatus.CREATED
        ).distinct().order_by('-created_at')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsSupplier],
            url_path='supplier-orders-details')
    def retrieve_supplier_order(self, request, pk=None):
        try:
            order = Order.objects.for_supplier(request.user).filter(pk=pk).first()
            serializer = self.get_serializer(order)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"message": "Order not found or you don't have permission to view it."},
                            status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='ready-to-ship', permission_classes=[IsAuthenticated, IsSupplier])
    def ready_to_ship(self, request, pk=None):
        user = request.user
        try:
            shipment = Shipment.objects.get(
                order__pk=pk,
                supplier=user.supplier,
                status=Shipment.ShipmentStatus.CREATED
            )
        except Shipment.DoesNotExist:
            return Response({"message": "Shipment not found or is not in a 'created' state."},
                            status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            shipment.status = Shipment.ShipmentStatus.READY_TO_SHIP
            shipment.save()
            if shipment.order:
                shipment.order.status = Order.OrderStatus.READY_TO_SHIP
                shipment.order.save()

        return Response({"message": f"Shipment for order {pk} is now ready to ship."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_order_by_user(self, request, pk=None):
        try:
            order = Order.objects.get(pk=pk, user=request.user)

            if order.status in [Order.OrderStatus.CREATED, Order.OrderStatus.In_Transmit]:
                with transaction.atomic():
                    order.status = Order.OrderStatus.CANCELLED
                    order.save()

                    cashback_amount = order.final_amount * Decimal('0.05')
                    user = request.user

                    if order.payment_method == Order.PaymentMethod.BALANCE:
                        user.Balance += order.final_amount
                        user.Balance -= cashback_amount
                        Transaction.objects.create(user=user, transaction_type=Transaction.TransactionType.CASH_BACK,
                                                   amount=-cashback_amount)
                        Transaction.objects.create(user=user,
                                                   transaction_type=Transaction.TransactionType.RETURNED_PRODUCT,
                                                   amount=order.final_amount)
                    elif order.payment_method == Order.PaymentMethod.CREDIT_CARD and order.paid:
                        user.Balance += order.final_amount
                        user.Balance -= cashback_amount
                        Transaction.objects.create(user=user,
                                                   transaction_type=Transaction.TransactionType.RETURNED_CASH_BACK,
                                                   amount=-cashback_amount)
                        Transaction.objects.create(user=user,
                                                   transaction_type=Transaction.TransactionType.RETURNED_PRODUCT,
                                                   amount=order.final_amount)
                    elif order.payment_method == Order.PaymentMethod.CASH_ON_DELIVERY:
                        user.Balance -= cashback_amount
                        Transaction.objects.create(user=user,
                                                   transaction_type=Transaction.TransactionType.RETURNED_CASH_BACK,
                                                   amount=-cashback_amount)

                return Response({"message": "Order has been cancelled."}, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"message": "Cannot cancel an order that has been delivered or marked as failed delivery."},
                    status=status.HTTP_400_BAD_REQUEST)

        except Order.DoesNotExist:
            return Response({"message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], url_path='calculate-totals')
    def calculate_totals(self, request, *args, **kwargs):
        cart = Cart.objects.get(User=request.user)
        address_id = request.data.get("address_id")
        coupon_code = request.data.get("coupon_code")

        cache_key = f"cart_totals:{cart.id}:{address_id}:{coupon_code}"
        totals = cache.get(cache_key)

        if not totals:
            _validate_request_data(cart, address_id, "")
            address = Address.objects.filter(user=request.user, id=address_id).first()
            if not address:
                raise ValidationError("Address not found or does not belong to the user.")

            cart_items = CartItems.objects.filter(CartID=cart)
            _validate_cart_stock(cart_items)

            totals = _calculate_all_order_totals_helper(cart_items, coupon_code, address, request.user)
            cache.set(cache_key, totals, 60 * 15)

        return Response({
            "message": "Order totals calculated successfully",
            **totals
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        cart = Cart.objects.get(User=request.user)
        address_id = request.data.get("address_id")
        coupon_code = request.data.get("coupon_code")
        payment_method = request.data.get("payment_method", "").strip()

        _validate_request_data(cart, address_id, payment_method)
        address = Address.objects.filter(user=request.user, id=address_id).first()
        cart_items = CartItems.objects.filter(CartID=cart)

        _validate_cart_stock(cart_items)

        if payment_method == Order.PaymentMethod.CREDIT_CARD:
            return Response({
                "message": "Redirecting to payment gateway...",
                "status": "pending_payment"
            }, status=status.HTTP_200_OK)

        if payment_method == Order.PaymentMethod.BALANCE:
            totals = _calculate_all_order_totals_helper(cart_items, coupon_code, address, request.user)
            if request.user.Balance < totals['final_amount']:
                raise ValidationError({"message": "Insufficient balance for this order."})

        create_order_task.delay(
            user_id=request.user.id,
            cart_id=cart.id,
            address_id=address_id,
            coupon_code=coupon_code,
            payment_method=payment_method
        )

        return Response({
            "message": "Your order is being processed.",
        }, status=status.HTTP_202_ACCEPTED)


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

            if shipment.order:
                order = shipment.order
                if not order.shipments.exclude(status=Shipment.ShipmentStatus.ON_MY_WAY).exists():
                    order.status = Order.OrderStatus.ON_MY_WAY
                    order.save()

                send_order_notification_task.delay(
                    user_id=order.user.id,
                    message=f"A delivery person is on their way with a shipment for your order #{order.order_number}.",
                    order_id=str(order.id)
                )
                send_order_notification_task.delay(
                    user_id=shipment.supplier.user.id,
                    message=f"Your shipment for order #{order.order_number} has been picked up by a delivery person.",
                    order_id=str(order.id)
                )

        return Response({'status': 'Shipment accepted and status updated to on my way'})

    @action(detail=True, methods=['post'], url_path='delivered')
    def delivered(self, request, pk=None):
        try:
            shipment = self.get_queryset().get(pk=pk, delivery_person=request.user.delivery)
        except Shipment.DoesNotExist:
            return Response({'message': 'Shipment not found or you are not assigned to it.'},
                            status=status.HTTP_404_NOT_FOUND)

        confirmation_code = request.data.get('confirmation_code')
        if confirmation_code != shipment.confirmation_code:
            return Response({"message": "Invalid confirmation code."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            warehouse = get_warehouse_by_name(shipment.to_state)

            shipment.status = Shipment.ShipmentStatus.DELIVERED_SUCCESSFULLY
            shipment.delivery_confirmed_at = timezone.now()
            shipment.save()

            if shipment.order:
                order = shipment.order
                if all(s.status == Shipment.ShipmentStatus.DELIVERED_SUCCESSFULLY for s in order.shipments.all()):
                    order.status = Order.OrderStatus.DELIVERED_SUCCESSFULLY
                    order.save()

                process_payments_task.delay(request.user.id, str(shipment.id), str(warehouse.id))

                send_order_notification_task.delay(
                    user_id=order.user.id,
                    message=f"A shipment for your order #{order.order_number} has been successfully delivered!",
                    order_id=str(order.id)
                )

        return Response({'message': 'Shipment status updated to delivered successfully'}, status=status.HTTP_200_OK)


class ReturnOrdersProductsViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ReturnRequestListRetrieveSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        fourteen_days_ago = timezone.now() - datetime.timedelta(days=14)
        if hasattr(user, 'is_customer') and user.is_customer:
            return Order.objects.filter(user=user, updated_at__gte=fourteen_days_ago)
        return Order.objects.none()


class CouponViewSet(viewsets.ModelViewSet):
    serializer_class = CouponSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if hasattr(self.request.user, 'supplier'):
            return Coupon.objects.filter(supplier=self.request.user.supplier)
        return Coupon.objects.filter(active=True)

    def perform_create(self, serializer):
        coupon = serializer.save(supplier=self.request.user.supplier)
        supplier_products = Product.objects.filter(Supplier=self.request.user.supplier)
        coupon.products.set(supplier_products)

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.supplier != self.request.user.supplier:
            return Response({"message": "You do not have permission to perform this action."},
                            status=status.HTTP_403_FORBIDDEN)
        serializer.save()
        supplier_products = Product.objects.filter(Supplier=self.request.user.supplier)
        instance.products.set(supplier_products)

    def perform_destroy(self, instance):
        if instance.supplier != self.request.user.supplier:
            return Response({"message": "You do not have permission to perform this action."},
                            status=status.HTTP_403_FORBIDDEN)
        instance.delete()
        return Response({"message": "Coupon deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class WarehouseListView(generics.ListAPIView):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer