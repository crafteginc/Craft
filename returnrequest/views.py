from django.core.exceptions import ValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from orders.models import Shipment
from .models import BalanceWithdrawRequest, ReturnRequest, Transaction
from .permissions import (IsAssignedDeliveryPerson, IsRequestSupplier,
                          IsReturnRequestOwner)
from .serializers import (BalanceWithdrawRequestSerializer,
                          ReturnRequestCreateSerializer,
                          ReturnRequestDetailSerializer,
                          ReturnRequestListSerializer, TransactionSerializer)
from .tasks import (
    process_supplier_approval_task,  
    approve_withdrawal_task,
    cancel_return_request_task,
    create_return_request_task,
    create_withdrawal_request_task,
    reject_return_request_task,
    reject_withdrawal_task
)


class ReturnRequestViewSet(viewsets.ModelViewSet):
    queryset = ReturnRequest.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = ReturnRequest.objects.for_user(user).select_related(
            'user', 'product__Supplier', 'order'
        ).prefetch_related('shipments')
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return ReturnRequestCreateSerializer
        if self.action in ['list', 'new', 'accepted', 'rejected']:
            return ReturnRequestListSerializer
        return ReturnRequestDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        create_return_request_task.delay(
            user_id=request.user.id,
            product_id=serializer.validated_data['product'].id,
            order_id=serializer.validated_data['order'].id,
            quantity=serializer.validated_data['quantity'],
            reason=serializer.validated_data['reason'],
            image_path=serializer.validated_data.get('image')
        )
        
        return Response(
            {"message": "Your return request is being processed."},
            status=status.HTTP_202_ACCEPTED
        )

    @action(detail=False, methods=['get'])
    def new(self, request):
        queryset = self.get_queryset().filter(status=ReturnRequest.ReturnStatus.NEW)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def accepted(self, request):
        queryset = self.get_queryset().filter(status=ReturnRequest.ReturnStatus.ACCEPTED)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def rejected(self, request):
        rejected_statuses = [
            ReturnRequest.ReturnStatus.REJECTED,
            ReturnRequest.ReturnStatus.CANCELLED
        ]
        queryset = self.get_queryset().filter(status__in=rejected_statuses)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsRequestSupplier])
    def approve(self, request, pk=None):
        # ✨ FIX: Use the correct task name
        process_supplier_approval_task.delay(pk)
        return Response({'status': 'Approval is being processed.'}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'], permission_classes=[IsRequestSupplier])
    def reject(self, request, pk=None):
        reject_return_request_task.delay(pk)
        return Response({'status': 'Rejection is being processed.'}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'], permission_classes=[IsReturnRequestOwner])
    def cancel(self, request, pk=None):
        cancel_return_request_task.delay(pk)
        return Response({'status': 'Cancellation is being processed.'}, status=status.HTTP_202_ACCEPTED)


class BalanceWithdrawRequestViewSet(mixins.CreateModelMixin,
                                      mixins.ListModelMixin,
                                      mixins.RetrieveModelMixin,
                                      viewsets.GenericViewSet):
    serializer_class = BalanceWithdrawRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return BalanceWithdrawRequest.objects.all()
        return BalanceWithdrawRequest.objects.filter(user=user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        create_withdrawal_request_task.delay(
            user_id=request.user.id,
            amount=str(serializer.validated_data['amount']),  # Convert Decimal to string
            transfer_number=serializer.validated_data['transfer_number'],
            transfer_type=serializer.validated_data['transfer_type'],
            notes=serializer.validated_data.get('notes')
        )
        
        return Response(
            {"message": "Your withdrawal request is being processed."},
            status=status.HTTP_202_ACCEPTED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        admin_notes = request.data.get('admin_notes', '')
        approve_withdrawal_task.delay(pk, request.user.id, admin_notes)
        return Response({'status': 'Approval is being processed.'}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        admin_notes = request.data.get('admin_notes')
        if not admin_notes:
            return Response({'detail': 'Admin notes are required for rejection.'}, status=status.HTTP_400_BAD_REQUEST)
        
        reject_withdrawal_task.delay(pk, request.user.id, admin_notes)
        return Response({'status': 'Rejection is being processed.'}, status=status.HTTP_202_ACCEPTED)


class TransactionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Transaction.objects.all()
        return Transaction.objects.filter(user=self.request.user)