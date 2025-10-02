from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from orders.models import Shipment
from .models import BalanceWithdrawRequest, ReturnRequest, Transaction
from .permissions import (IsAssignedDeliveryPerson, IsRequestSupplier,
                          IsReturnRequestOwner)
from .serializers import (BalanceWithdrawRequestSerializer,
                          ReturnRequestCreateSerializer,
                          ReturnRequestDetailSerializer,
                          ReturnRequestListSerializer, TransactionSerializer)
from .services import BalanceService, ReturnRequestService

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
        try:
            return_request = ReturnRequestService.create_return_request(
                user=self.request.user, **serializer.validated_data
            )
            response_serializer = ReturnRequestDetailSerializer(return_request, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=False, methods=['get'])
    def new(self, request):
        """
        Returns a list of all new (pending approval) return requests.
        """
        queryset = self.get_queryset().filter(status=ReturnRequest.ReturnStatus.NEW)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def accepted(self, request):
        """
        Returns a list of all accepted (completed) return requests.
        """
        queryset = self.get_queryset().filter(status=ReturnRequest.ReturnStatus.ACCEPTED)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def rejected(self, request):
        """
        Returns a list of all rejected or cancelled return requests.
        """
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
        return_request = self.get_object()
        try:
            ReturnRequestService.process_supplier_approval(return_request)
            return Response({'status': 'Return approved and funds processed.'})
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[IsRequestSupplier])
    def reject(self, request, pk=None):
        return_request = self.get_object()
        try:
            ReturnRequestService.reject_return_request(return_request)
            return Response({'status': 'Return request has been rejected.'})
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsReturnRequestOwner])
    def cancel(self, request, pk=None):
        return_request = self.get_object()
        try:
            ReturnRequestService.cancel_return_request(return_request)
            return Response({'status': 'Return request and associated shipments have been cancelled.'})
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class BalanceWithdrawRequestViewSet(mixins.CreateModelMixin,
                                      mixins.ListModelMixin,
                                      mixins.RetrieveModelMixin,
                                      viewsets.GenericViewSet):
    serializer_class = BalanceWithdrawRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BalanceWithdrawRequest.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            withdrawal_request = BalanceService.create_withdrawal_request(
                user=request.user, **serializer.validated_data
            )
            response_serializer = self.get_serializer(withdrawal_request)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"detail": e.message}, status=status.HTTP_400_BAD_REQUEST)

class TransactionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)