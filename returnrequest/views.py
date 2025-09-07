from rest_framework import generics, serializers
from .models import Balance_Withdraw_Request, transactions, ReturnRequest
from accounts.models import Address
from products.models import Product
from orders.models import Order
from .serializers import (BalanceWithdrawRequestSerializer, TransactionSerializer,
                          ReturnRequestListRetrieveSerializer, ReturnRequestCreateSerializer,
                          ReturnRequestDeliverSerializer)
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Q
from rest_framework.decorators import action
from django.utils import timezone
from orders.services import get_craft_user_by_email, get_warehouse_by_name
from decimal import Decimal

Craft = get_craft_user_by_email("CraftEG@craft.com")
if Craft:
    print("User found:", Craft)
else:
    print("User not found.")

class ReturnRequestViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ReturnRequestCreateSerializer
    queryset = ReturnRequest.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ReturnRequest.objects.none()

        if hasattr(user, 'delivery'):
            return ReturnRequest.objects.filter(
                Q(status=ReturnRequest.ReturnStatus.PICKUP_SCHEDULED) & Q(from_state=user.delivery.governorate) |
                Q(status=ReturnRequest.ReturnStatus.IN_TRANSIT_TO_WAREHOUSE) & Q(to_state=user.delivery.governorate) |
                Q(status=ReturnRequest.ReturnStatus.IN_TRANSIT_TO_SUPPLIER) & Q(to_state=user.delivery.governorate) |
                Q(delivery_person=user.delivery)
            )
        elif hasattr(user, 'supplier'):
            return ReturnRequest.objects.filter(
                Q(supplier=user.supplier) |
                Q(status=ReturnRequest.ReturnStatus.DELIVERED_SUCCESSFULLY) & Q(supplier=user.supplier)
            )
        else: # Customer
            return ReturnRequest.objects.filter(user=user)

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return ReturnRequestListRetrieveSerializer
        return self.serializer_class

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product = Product.objects.get(id=serializer.validated_data.get('product_id'))
        order = Order.objects.get(id=serializer.validated_data.get('order_id'))
        quantity = serializer.validated_data.get('quantity')
        
        user = request.user
        customer_address = Address.objects.get(id=order.address.id)
        supplier_address = Address.objects.get(user=product.Supplier.user)
        
        with transaction.atomic():
            amount = product.UnitPrice * Decimal(quantity)

            if customer_address.State == supplier_address.State:
                return_request = ReturnRequest.objects.create(
                    user=user,
                    supplier=product.Supplier,
                    product=product,
                    order=order,
                    quantity=quantity,
                    amount=amount,
                    from_address=customer_address,
                    to_address=supplier_address,
                    from_state=customer_address.State,
                    to_state=supplier_address.State,
                    status=ReturnRequest.ReturnStatus.PICKUP_SCHEDULED,
                )
            else:
                warehouse_address = get_warehouse_by_name(customer_address.State).Address
                return_request = ReturnRequest.objects.create(
                    user=user,
                    supplier=product.Supplier,
                    product=product,
                    order=order,
                    quantity=quantity,
                    amount=amount,
                    from_address=customer_address,
                    to_address=warehouse_address,
                    from_state=customer_address.State,
                    to_state=warehouse_address.State,
                    status=ReturnRequest.ReturnStatus.PICKUP_SCHEDULED,
                )

        return Response({
            "message": "Return request created successfully. Our shipping driver will contact you.",
            "return_request_id": return_request.id,
            "total_amount": return_request.amount,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='delivery-accept')
    def delivery_accept(self, request, pk=None):
        try:
            return_request = self.get_queryset().get(pk=pk, delivery_person=None)
        except ReturnRequest.DoesNotExist:
            return Response({'detail': 'Return request not found or is already taken.'}, status=status.HTTP_404_NOT_FOUND)
        
        with transaction.atomic():
            return_request.delivery_person = request.user.delivery
            return_request.status = ReturnRequest.ReturnStatus.IN_TRANSIT_TO_WAREHOUSE
            return_request.save()
        
        return Response({'status': 'Return request accepted and status updated to in transit to warehouse.'})

    @action(detail=True, methods=['post'], url_path='delivered-to-warehouse')
    def delivered_to_warehouse(self, request, pk=None):
        try:
            return_request = self.get_queryset().get(pk=pk, delivery_person=request.user.delivery)
        except ReturnRequest.DoesNotExist:
            return Response({'detail': 'Return request not found or you are not assigned to it.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReturnRequestDeliverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirmation_code = serializer.validated_data.get('confirmation_code')

        if confirmation_code != return_request.confirmation_code:
            return Response({"detail": "Invalid confirmation code."}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            return_request.status = ReturnRequest.ReturnStatus.DELIVERED_TO_WAREHOUSE
            return_request.delivery_confirmed_at = timezone.now()
            return_request.save()
        
        return Response({'status': 'Return request status updated to delivered to warehouse.'})

    @action(detail=True, methods=['post'], url_path='supplier-accept')
    def supplier_accept(self, request, pk=None):
        return_request = self.get_object()
        user = request.user

        if not hasattr(user, 'supplier') or return_request.supplier.user != user:
            return Response({'detail': 'You are not authorized to accept this return request.'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            return_amount = return_request.amount
            return_request.user.Balance += return_amount
            user.supplier.Balance -= return_amount
            
            transactions.objects.create(user=return_request.user, transaction_type=transactions.TransactionType.RETURNED_PRODUCT, amount=return_amount)
            transactions.objects.create(user=user, transaction_type=transactions.TransactionType.RETURNED_PRODUCT, amount=-return_amount)

            return_request.status = ReturnRequest.ReturnStatus.ACCEPTED_BY_SUPPLIER
            return_request.save()

        return Response({'status': 'Return request accepted and balances updated'})
    
    @action(detail=True, methods=['post'], url_path='supplier-reject')
    def supplier_reject(self, request, pk=None):
        return_request = self.get_object()
        user = request.user

        if not hasattr(user, 'supplier') or return_request.supplier.user != user:
            return Response({'detail': 'You are not authorized to reject this return request.'}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            return_request.status = ReturnRequest.ReturnStatus.REJECTED_BY_SUPPLIER
            return_request.save()
        
        return Response({'status': 'Return request rejected'})
    
    @action(detail=True, methods=['post'], url_path='cancel', url_name='cancel-order')
    def cancel_order(self, request, pk=None):
        try:
            user = request.user
            return_request = ReturnRequest.objects.get(pk=pk, user=user)

            if return_request.status != ReturnRequest.ReturnStatus.CREATED:
                return Response({"detail": "Cannot cancel a return request after it has been shipped."}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                return_request.status = ReturnRequest.ReturnStatus.CANCELLED
                return_request.save()
            
            return Response({"detail": "Return request has been cancelled."}, status=status.HTTP_200_OK)
        except ReturnRequest.DoesNotExist:
            return Response({"detail": "Return request not found."}, status=status.HTTP_404_NOT_FOUND)        

class BalanceWithdrawRequestListCreateView(generics.ListCreateAPIView):
    queryset = Balance_Withdraw_Request.objects.all()
    serializer_class = BalanceWithdrawRequestSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        amount = self.request.data.get("amount")
        
        if user.Balance < Decimal(amount):
            raise serializers.ValidationError("Insufficient balance for this withdrawal.")
        
        with transaction.atomic():
            user.Balance -= Decimal(amount)
            transactions.objects.create(user=user, transaction_type=transactions.TransactionType.WITHDRAW, amount=-Decimal(amount))
            user.save()

        serializer.save(user=user)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['user'] = request.user.id
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response(f"Your withdrawal request has been created. You will receive your amount soon. {serializer.data} ", status=status.HTTP_201_CREATED, headers=headers)
   
class BalanceWithdrawRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Balance_Withdraw_Request.objects.all()
    serializer_class = BalanceWithdrawRequestSerializer
    permission_classes = [IsAuthenticated]

@api_view(['GET'])
def get_user_transactions(request):
    transactions_data = transactions.objects.filter(user=request.user)
    serializer = TransactionSerializer(transactions_data, many=True)
    return Response(serializer.data)