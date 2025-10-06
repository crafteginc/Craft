from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from accounts.models import Address, User
from orders.models import Shipment, ShipmentItem, Order, Product
from orders.services import get_warehouse_by_name
from notifications.services import create_notification_for_user

from .models import BalanceWithdrawRequest, ReturnRequest, Transaction


class ReturnRequestService:
    @staticmethod
    @transaction.atomic
    def create_return_request_logic(
        user_id, product_id, order_id, quantity, reason, image=None
    ) -> ReturnRequest:
        user = get_object_or_404(User, id=user_id)
        product = get_object_or_404(Product, id=product_id)
        order = get_object_or_404(Order, id=order_id)
        customer_address = order.address
        supplier_address = get_object_or_404(Address, user=product.Supplier.user)

        return_request = ReturnRequest.objects.create(
            user=user,
            order=order,
            product=product,
            supplier=product.Supplier,
            quantity=quantity,
            amount=product.UnitPrice * Decimal(quantity),
            reason=reason,
            image=image,
            status=ReturnRequest.ReturnStatus.NEW,
        )

        create_notification_for_user(
            user=user,
            message=f"Your return request for '{product.ProductName}' has been submitted.",
            related_object=return_request,
            image=image
        )
        create_notification_for_user(
            user=product.Supplier.user,
            message=f"You have received a new return request for '{product.ProductName}'.",
            related_object=return_request,
            image=image
        )

        customer_state = customer_address.State
        supplier_state = supplier_address.State

        if customer_state == supplier_state:
            shipment = Shipment.objects.create(
                return_request=return_request,
                supplier=product.Supplier,
                from_address=customer_address,
                to_address=supplier_address,
                from_state=customer_state,
                to_state=supplier_state,
                status=Shipment.ShipmentStatus.CREATED,
            )
            ShipmentItem.objects.create(
                shipment=shipment, return_request=return_request, quantity=quantity
            )
        else:
            warehouse_source = get_warehouse_by_name(customer_state)
            
            shipment1 = Shipment.objects.create(
                return_request=return_request,
                supplier=product.Supplier,
                from_address=customer_address,
                to_address=warehouse_source.Address,
                from_state=customer_state,
                to_state=customer_state,
                status=Shipment.ShipmentStatus.CREATED
            )
            ShipmentItem.objects.create(shipment=shipment1, return_request=return_request, quantity=quantity)

            shipment2 = Shipment.objects.create(
                return_request=return_request,
                supplier=product.Supplier,
                from_address=warehouse_source.Address,
                to_address=supplier_address,
                from_state=customer_state,
                to_state=supplier_state,
                status=Shipment.ShipmentStatus.In_Transmit
            )
            ShipmentItem.objects.create(shipment=shipment2, return_request=return_request, quantity=quantity)
        
        return return_request

    @staticmethod
    @transaction.atomic
    def process_supplier_approval(return_request: ReturnRequest):
        if return_request.status != ReturnRequest.ReturnStatus.NEW:
            raise ValidationError(
                f"This return request cannot be approved. Its current status is '{return_request.get_status_display()}'."
            )

        final_shipment = return_request.shipments.order_by("-created_at").first()
        if (
            not final_shipment
            or final_shipment.status != Shipment.ShipmentStatus.DELIVERED_SUCCESSFULLY
        ):
            raise ValidationError(
                "Return cannot be approved until the item has been delivered to the supplier."
            )

        return_amount = return_request.amount
        customer = return_request.user
        supplier_user = return_request.supplier.user

        customer.Balance += return_amount
        supplier_user.Balance -= return_amount
        customer.save(update_fields=["Balance"])
        supplier_user.save(update_fields=["Balance"])

        Transaction.objects.create(
            user=customer,
            transaction_type=Transaction.TransactionType.RETURN_CREDIT,
            amount=return_amount,
            related_object=return_request,
        )
        Transaction.objects.create(
            user=supplier_user,
            transaction_type=Transaction.TransactionType.RETURN_DEBIT,
            amount=-return_amount,
            related_object=return_request,
        )

        return_request.approve_by_supplier()

        create_notification_for_user(
            user=customer,
            message=f"Your return request for '{return_request.product.ProductName}' has been approved.",
            related_object=return_request
        )

    @staticmethod
    def reject_return_request(return_request: ReturnRequest):
        if return_request.status != ReturnRequest.ReturnStatus.NEW:
            raise ValidationError(
                f"This return request cannot be rejected. Its current status is '{return_request.get_status_display()}'."
            )

        final_shipment = return_request.shipments.order_by("-created_at").first()
        if (
            not final_shipment
            or final_shipment.status != Shipment.ShipmentStatus.DELIVERED_SUCCESSFULLY
        ):
            raise ValidationError(
                "Return cannot be rejected until the item has been delivered to you."
            )

        return_request.reject_by_supplier()

        create_notification_for_user(
            user=return_request.user,
            message=f"Your return request for '{return_request.product.ProductName}' has been rejected.",
            related_object=return_request
        )

    @staticmethod
    @transaction.atomic
    def cancel_return_request(return_request: ReturnRequest):
        cancellable_statuses = [
            Shipment.ShipmentStatus.CREATED,
            Shipment.ShipmentStatus.READY_TO_SHIP,
        ]
        shipments = return_request.shipments.select_for_update().all()

        if not shipments.exists():
            return_request.cancel()
        else:
            for shipment in shipments:
                if shipment.status not in cancellable_statuses:
                    raise ValidationError(
                        f"Cannot cancel. A shipment for this return is already in progress (status: {shipment.get_status_display()})."
                    )
            shipments.update(status=Shipment.ShipmentStatus.CANCELLED)
            return_request.cancel()
        
        create_notification_for_user(
            user=return_request.user,
            message=f"You have successfully cancelled your return request for '{return_request.product.ProductName}'.",
            related_object=return_request
        )
        create_notification_for_user(
            user=return_request.supplier.user,
            message=f"The return request for '{return_request.product.ProductName}' has been cancelled by the customer.",
            related_object=return_request
        )


class BalanceService:
    @staticmethod
    def _run_fraud_check(request: BalanceWithdrawRequest):
        if request.amount > 1000:
            request.risk_score = 75.0
            request.transfer_status = (
                BalanceWithdrawRequest.TransferStatus.AWAITING_APPROVAL
            )
            request.admin_notes = "Flagged for manual review due to high amount."
        else:
            request.risk_score = 10.0
            request.transfer_status = BalanceWithdrawRequest.TransferStatus.AWAITING_APPROVAL
        request.save()

    @staticmethod
    @transaction.atomic
    def create_withdrawal_request_logic(
        user_id, amount: Decimal, transfer_number: str, transfer_type: str, notes: str = None
    ) -> BalanceWithdrawRequest:
        user = get_object_or_404(User, id=user_id)
        if user.Balance < amount:
            raise ValidationError("Insufficient balance for this withdrawal.")

        if amount <= 0:
            raise ValidationError("Withdrawal amount must be positive.")

        user.Balance -= amount
        user.save(update_fields=["Balance"])

        transaction_log = Transaction.objects.create(
            user=user,
            transaction_type=Transaction.TransactionType.WITHDRAWAL_REQUEST,
            amount=-amount,
        )

        withdrawal_request = BalanceWithdrawRequest.objects.create(
            user=user,
            amount=amount,
            transfer_number=transfer_number,
            transfer_type=transfer_type,
            notes=notes,
            related_transaction=transaction_log,
        )

        BalanceService._run_fraud_check(withdrawal_request)

        create_notification_for_user(
            user=user,
            message=f"Your withdrawal request for EGP {amount:.2f} has been submitted for review.",
            related_object=withdrawal_request
        )

        return withdrawal_request

    @staticmethod
    @transaction.atomic
    def approve_withdrawal(request: BalanceWithdrawRequest, admin_user_id, admin_notes: str):
        admin_user = get_object_or_404(User, id=admin_user_id)
        if request.transfer_status != BalanceWithdrawRequest.TransferStatus.AWAITING_APPROVAL:
            raise ValidationError("This request is not awaiting approval.")

        request.transfer_status = BalanceWithdrawRequest.TransferStatus.APPROVED
        request.admin_notes = admin_notes
        request.admin_notes += f"\nManually approved by {admin_user.get_full_name} on {timezone.now().strftime('%Y-%m-%d %H:%M')}."
        request.save()

        create_notification_for_user(
            user=request.user,
            message=f"Your withdrawal request for EGP {request.amount:.2f} has been approved.",
            related_object=request
        )

    @staticmethod
    @transaction.atomic
    def reject_withdrawal(request: BalanceWithdrawRequest, admin_user_id, admin_notes: str):
        admin_user = get_object_or_404(User, id=admin_user_id)
        if request.transfer_status not in [
            BalanceWithdrawRequest.TransferStatus.AWAITING_APPROVAL,
            BalanceWithdrawRequest.TransferStatus.REQUESTED,
        ]:
            raise ValidationError("This request cannot be rejected.")

        original_status = request.transfer_status
        request.transfer_status = BalanceWithdrawRequest.TransferStatus.REJECTED
        request.admin_notes = admin_notes
        request.admin_notes += f"\nManually rejected by {admin_user.get_full_name} on {timezone.now().strftime('%Y-%m-%d %H:%M')}."
        request.save()

        create_notification_for_user(
            user=request.user,
            message=f"Your withdrawal request for EGP {request.amount:.2f} was rejected. Reason: {admin_notes}",
            related_object=request
        )

        if original_status == BalanceWithdrawRequest.TransferStatus.AWAITING_APPROVAL:
            user = request.user
            user.Balance += request.amount
            user.save(update_fields=["Balance"])

            Transaction.objects.create(
                user=user,
                transaction_type=Transaction.TransactionType.WITHDRAWAL_CANCELLED,
                amount=request.amount,
                related_object=request,
            )

    @staticmethod
    def process_approved_request(request: BalanceWithdrawRequest):
        if request.transfer_status != BalanceWithdrawRequest.TransferStatus.APPROVED:
            raise ValidationError("This request is not approved for processing.")

        request.transfer_status = BalanceWithdrawRequest.TransferStatus.PROCESSING
        request.save()

        # In a real scenario, this is where you would integrate with a payment gateway.
        # For now, we'll simulate a successful transfer.

        request.transfer_status = BalanceWithdrawRequest.TransferStatus.COMPLETED
        request.save()

        Transaction.objects.create(
            user=request.user,
            transaction_type=Transaction.TransactionType.WITHDRAWAL_COMPLETED,
            amount=-request.amount,
            related_object=request,
        )

        create_notification_for_user(
            user=request.user,
            message=f"Your withdrawal of EGP {request.amount:.2f} is complete and has been sent.",
            related_object=request
        )