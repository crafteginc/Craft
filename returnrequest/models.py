import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class ReturnRequestManager(models.Manager):
    def for_user(self, user):
        if not user.is_authenticated:
            return self.none()
        if hasattr(user, 'delivery'):
            return self.filter(shipments__delivery_person=user.delivery)
        elif hasattr(user, 'supplier'):
            return self.filter(supplier=user.supplier)
        else: # Customer
            return self.filter(user=user)

class ReturnRequest(models.Model):
    class ReturnStatus(models.TextChoices):
        PENDING_APPROVAL = 'pending_approval', _('Pending Approval')
        COMPLETED = 'completed', _('Completed')
        REJECTED = 'rejected', _('Rejected')
        CANCELLED = 'cancelled', _('Cancelled')

    class ReturnReason(models.TextChoices):
        DAMAGED = 'damaged', _('Item was damaged')
        WRONG_ITEM = 'wrong_item', _('Received wrong item')
        WRONG_SIZE = 'wrong_size', _('Wrong size or fit')
        NOT_AS_DESCRIBED = 'not_as_described', _('Not as described')
        CHANGED_MIND = 'changed_mind', _('Changed my mind')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='return_requests')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    supplier = models.ForeignKey('accounts.Supplier', on_delete=models.CASCADE, related_name="return_requests")
    
    status = models.CharField(max_length=50, choices=ReturnStatus.choices, default=ReturnStatus.PENDING_APPROVAL)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=50, choices=ReturnReason.choices)
    image = models.ImageField(upload_to='returns/%Y/%m/%d/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ReturnRequestManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return f"Return Request #{self.pk} for {self.product.ProductName}"

    def approve_by_supplier(self):
        self.status = self.ReturnStatus.COMPLETED
        self.save()

    def reject_by_supplier(self):
        self.status = self.ReturnStatus.REJECTED
        self.save()

    def cancel(self):
        self.status = self.ReturnStatus.CANCELLED
        self.save()

class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        
        WITHDRAWAL_REQUEST = 'WITHDRAWAL_REQUEST', _('Withdrawal Request')
        RETURN_CREDIT = 'RETURN_CREDIT', _('Return Credit')
        RETURN_DEBIT = 'RETURN_DEBIT', _('Return Debit')
        CASH_BACK = 'CASH_BACK', _('Cash Back')
        RETURNED_CASH_BACK = 'RETURNED_CASH_BACK', _('Returned Cash Back')
        RETURNED_PRODUCT = 'RETURNED_PRODUCT', _('Returned Product')
        PURCHASED_PRODUCTS = 'PURCHASED_PRODUCTS', _('Purchased Products')
        DELIVERY_FEE = 'DELIVERY_FEE', _('Delivery Fee')
        SUPPLIER_TRANSFORM = 'SUPPLIER_TRANSFORM', _('Supplier Transform')
        REFUND_FAILED = 'REFUND_FAILED', _('Refund Failed')
        PURCHASED_COURSE = 'PURCHASED_COURSE', _('Purchased Course')


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=50, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_transaction_type_display()} of {self.amount} for {self.user.get_full_name}"

class BalanceWithdrawRequest(models.Model):
    class TransferStatus(models.TextChoices):
        CREATED = 'Created'
        DONE = 'Done'
        REFUSED = 'Refused'

    class TransferType(models.TextChoices):
        BANK_TRANSFER = 'Bank Transfer'
        INSTAPAY = 'Instapay'
        PHONE_WALLET = 'Phone Wallet'
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    related_transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT, null=True)
    transfer_number = models.CharField(max_length=50)
    transfer_type = models.CharField(max_length=50, choices=TransferType.choices, default=TransferType.BANK_TRANSFER)
    transfer_status = models.CharField(max_length=50, choices=TransferStatus.choices, default=TransferStatus.CREATED)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Balance Withdraw Request"
        ordering = ['-created_at']