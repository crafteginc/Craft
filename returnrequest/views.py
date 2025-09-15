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
        return ReturnRequest.objects.for_user(self.request.user).select_related(
            'user', 'product__Supplier', 'order'
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return ReturnRequestCreateSerializer
        if self.action == 'list':
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

    @action(detail=True, methods=['post'], permission_classes=[IsRequestSupplier])
    def approve(self, request, pk=None):
        """
        Allows a supplier to approve a return request after delivery.
        This triggers the financial settlement via the service layer.
        """
        return_request = self.get_object()
        try:
            # Delegate all logic, including validation, to the service layer
            ReturnRequestService.process_supplier_approval(return_request)
            return Response({'status': 'Return approved and funds processed.'})
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[IsRequestSupplier])
    def reject(self, request, pk=None):
        """
        Allows a supplier to reject a return request after delivery and inspection.
        """
        return_request = self.get_object()
        
        # Get the final shipment leg to check its status
        final_shipment = return_request.shipments.order_by('-created_at').first()

        # VALIDATION: Ensure the item has been delivered before it can be rejected.
        if not final_shipment or final_shipment.status != Shipment.ShipmentStatus.DELIVERED_SUCCESSFULLY:
            return Response(
                {"detail": "Return cannot be rejected until the item has been delivered to you."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update the status
        return_request.reject_by_supplier()
        return Response({'status': 'Return request has been rejected.'})

    @action(detail=True, methods=['post'], permission_classes=[IsReturnRequestOwner])
    def cancel(self, request, pk=None):
        """
        Allows a user to cancel a return request if it has not been picked up.
        """
        return_request = self.get_object()
        
        cancellable_statuses = [
            Shipment.ShipmentStatus.CREATED,
            Shipment.ShipmentStatus.READY_TO_SHIP,
        ]

        try:
            with transaction.atomic():
                shipments = return_request.shipments.select_for_update().all()

                if not shipments.exists():
                    return_request.cancel()
                    return Response({'status': 'Return request cancelled.'})

                for shipment in shipments:
                    if shipment.status not in cancellable_statuses:
                        raise ValidationError(
                            f"Cannot cancel. A shipment for this return is already in progress (status: {shipment.get_status_display()})."
                        )
                
                shipments.update(status=Shipment.ShipmentStatus.CANCELLED)
                return_request.cancel()

            return Response({'status': 'Return request and all associated shipments have been cancelled.'})

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