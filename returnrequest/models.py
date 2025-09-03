from django.db import models
from django.conf import settings
from django.utils import timezone
from products.models import Product
from accounts.models import Supplier, User, Delivery, Address
from django.contrib.auth import get_user_model
from orders.models import Order
import uuid
import random
import string
from django.db.models import Q

User = get_user_model()
class ReturnRequest(models.Model):
    class ReturnStatus(models.TextChoices):
        CREATED = 'created', 'Created'
        PICKUP_SCHEDULED = 'pickup_scheduled', 'Pickup Scheduled'
        IN_TRANSIT_TO_WAREHOUSE = 'in_transit_to_warehouse', 'In Transit to Warehouse'
        DELIVERED_TO_WAREHOUSE = 'delivered_to_warehouse', 'Delivered to Warehouse'
        IN_TRANSIT_TO_SUPPLIER = 'in_transit_to_supplier', 'In Transit to Supplier'
        DELIVERED_SUCCESSFULLY = 'delivered_successfully', 'Delivered Successfully'
        FAILED_DELIVERY = 'failed_delivery', 'Failed Delivery'
        CANCELLED = 'cancelled', 'Cancelled'
        ACCEPTED_BY_SUPPLIER = 'accepted_by_supplier', 'Accepted by Supplier'
        REJECTED_BY_SUPPLIER = 'rejected_by_supplier', 'Rejected by Supplier'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
    quantity = models.IntegerField()
    delivery_person = models.ForeignKey(Delivery, on_delete=models.CASCADE, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="returned_Supplier_orders", null=True)
    from_address = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="returned_order_from_address", null=True)
    to_address = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="returned_order_to_address", null=True)
    from_state = models.CharField(max_length=250, blank=True)
    to_state = models.CharField(max_length=250, blank=True)
    confirmation_code = models.CharField(max_length=6, null=True, blank=True)
    delivery_confirmed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=ReturnStatus.choices, default=ReturnStatus.CREATED)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.confirmation_code:
            self.confirmation_code = ''.join(random.choices(string.digits, k=4))
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"ReturnRequest #{self.pk} - {self.user} returning {self.product}"

class Balance_Withdraw_Request(models.Model):
    class TransferStatus(models.TextChoices):
        CREATED = 'Created'
        DONE = 'Done'
        Refused = 'Refused'
    class TransferType(models.TextChoices):
        BANK_TRANSFER = 'Bank Transfer'
        INSTAPAY = 'Instapay'
        PHONE_WALLET = 'Phone Wallet'
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transfer_number = models.CharField(max_length=50)
    transfer_type = models.CharField(max_length=50, choices=TransferType.choices, default=TransferType.BANK_TRANSFER)
    transfer_status = models.CharField(max_length=50, choices=TransferStatus.choices, default=TransferStatus.CREATED)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    notes = models.TextField(null=True, blank=True)

class transactions(models.Model):
    class TransactionType(models.TextChoices):
        WITHDRAW = 'Withdraw'
        CASH_BACK = 'Cash Back'
        RETURNED_CASH_BACK = 'Returned Cash Back'
        RETURNED_PRODUCT = 'Returned Product'
        PURCHASED_PRODUCTS = 'Purshased Products'
        REFUND_FAILED = 'Refund Failed'
        DELIVERY_FEE = 'Delivery Fee'
        PURCHASED_COURSE = 'purchased Course'
        SUPPLIER_TRANSFORM = 'Supplier Transform'
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=50, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)