from django.utils.translation import gettext_lazy as _
from django.db import models
from products.models import Product
from accounts.models import User, Address, Supplier, Delivery
import uuid
from django.contrib.auth import get_user_model
from django.db.models import Q
import random
import string
from django.core.validators import MinValueValidator
from django.db.models.signals import pre_save
from django.dispatch import receiver

class OrderManager(models.Manager):
    def for_delivery_person(self, user):
        # ... (same as before)
        return self.filter(
            Q(shipments__from_state=user.delivery.governorate) &
            (Q(shipments__delivery_person=user) | Q(shipments__delivery_person__isnull=True)) &
            ~Q(shipments__status__in=[
                Shipment.ShipmentStatus.DELIVERED_SUCCESSFULLY,
                Shipment.ShipmentStatus.ON_MY_WAY,
                Shipment.ShipmentStatus.DELIVERED_TO_First_WAREHOUSE,
                Shipment.ShipmentStatus.CANCELLED,
                Shipment.ShipmentStatus.In_Transmit
            ])
        )

    def for_customer(self, user):
        """Returns orders for a specific customer, excluding certain statuses."""
        return self.filter(user=user).exclude(
            total_amount=0
        )

    def for_supplier(self, user):
        """Returns orders for a specific supplier (their sales)."""
        return self.filter(shipments__supplier=user.supplier)

    def for_supplier_as_customer(self, user):
        """Returns orders where the supplier is the customer (their purchases)."""
        return self.filter(user=user)

    def for_delivery(self, user):
        # ... (same as before)
        return self.filter(shipments__delivery_person=user)

class Wishlist(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    Created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Wishlist for: {self.user.get_full_name}"

class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlist_items')

    def __str__(self):
        return f"Wishlist Item: {self.product.ProductName}"

class Cart(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    User = models.OneToOneField(User, on_delete=models.CASCADE)
    Created_at = models.DateTimeField(auto_now_add=True,blank=True, null=True)

    def __str__(self):
        return f"Cart ID:{self.id} for {self.User.get_full_name}"

class CartItems(models.Model):
    CartID = models.ForeignKey(Cart, on_delete=models.CASCADE,related_name="items", null=True, blank=True)
    Product = models.ForeignKey(Product, on_delete=models.CASCADE,related_name='cartitems',null=True, blank=True)
    Quantity = models.PositiveIntegerField()
    Color = models.CharField(max_length=20,blank=True, null=True)
    Size = models.CharField(max_length=20,blank=True, null=True)

    def __str__(self):
        return f"Cart ID {self.CartID} Cart Item: {self.Product.ProductName}"

User = get_user_model()

class Order(models.Model):
    class OrderStatus(models.TextChoices):
        CREATED = 'created'
        READY_TO_SHIP ='ready_to_ship'
        ON_MY_WAY = 'on my way'
        DELIVERED_TO_First_WAREHOUSE = 'delivered to First warehouse'
        In_Transmit='In Transmit'
        DELIVERED_TO_Second_WAREHOUSE = 'delivered to Second warehouse'
        DELIVERED_SUCCESSFULLY = 'delivered successfully'
        FAILED_DELIVERY = 'failed delivery'
        CANCELLED = 'cancelled'

    class PaymentMethod(models.TextChoices):
        CASH_ON_DELIVERY = 'Cash on Delivery'
        CREDIT_CARD='Credit Card'
        BALANCE = 'Balance'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=10, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.ForeignKey(Address, on_delete=models.CASCADE )
    payment_method = models.CharField(max_length=50, choices=PaymentMethod.choices, default=PaymentMethod.CASH_ON_DELIVERY)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    delivery_fee =  models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    status = models.CharField(max_length=50, choices=OrderStatus.choices, default=OrderStatus.CREATED)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrderManager()

    def __str__(self):
        return f"Order ID: {self.id} for {self.user.email}"
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "created_at"])]

def generate_order_number():
    while True:
        order_number = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        if not Order.objects.filter(order_number=order_number).exists():
            return order_number

@receiver(pre_save, sender=Order)
def pre_save_order(sender, instance, **kwargs):
    if not instance.order_number:
        instance.order_number = generate_order_number()

class Shipment(models.Model):
    class ShipmentStatus(models.TextChoices):
        CREATED = 'created'
        READY_TO_SHIP ='ready_to_ship'
        ON_MY_WAY = 'on my way'
        DELIVERED_TO_First_WAREHOUSE = 'delivered to First warehouse'
        In_Transmit='In Transmit'
        DELIVERED_TO_Second_WAREHOUSE = 'delivered to Second warehouse'
        DELIVERED_SUCCESSFULLY = 'delivered successfully'
        FAILED_DELIVERY = 'failed delivery'
        CANCELLED = 'cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="shipments")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="shipments", null=True)
    delivery_person = models.ForeignKey(Delivery, on_delete=models.CASCADE, null=True)
    from_state = models.CharField(max_length=250, blank=True)
    to_state = models.CharField(max_length=250, blank=True)
    from_address = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="shipment_supplier_address", null=True, blank=True)
    to_address = models.ForeignKey(Address, on_delete=models.CASCADE, related_name="shipment_customer_address", null=True, blank=True)
    confirmation_code = models.CharField(max_length=6, null=True, blank=True)
    delivery_confirmed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=ShipmentStatus.choices, default=ShipmentStatus.CREATED)
    order_total_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def save(self, *args, **kwargs):
        if not self.confirmation_code:
            self.confirmation_code = ''.join(random.choices(string.digits, k=4))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Shipment for Order {self.order.id} from {self.supplier}"

class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    color = models.CharField(max_length=20,blank=True, null=True)
    size = models.CharField(max_length=20,blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"OrderItem {self.product.ProductName} for {self.order.user}"

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["order", "product"])]

    def get_cost(self):
        return self.price * self.quantity

class ShipmentItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name="items")
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="shipment_items")
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Shipment Item {self.order_item.product.ProductName} in Shipment {self.shipment.id}"

class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage'
        FIXED_AMOUNT = 'fixed_amount'

    supplier = models.ForeignKey(Supplier, related_name='coupons', on_delete=models.CASCADE)
    code = models.CharField(max_length=50, unique=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    discount_type = models.CharField(max_length=12, choices=DiscountType.choices, default=DiscountType.PERCENTAGE)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0)])
    max_uses = models.IntegerField(default=100)
    uses_count = models.IntegerField(default=0)
    max_uses_per_user = models.IntegerField(default=1)
    terms = models.TextField()
    products = models.ManyToManyField(Product, related_name='coupons', blank=True)

    def __str__(self):
        return self.code

class CouponUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'coupon')

class Warehouse(models.Model):
    name = models.CharField(max_length=100)
    Address = models.ForeignKey(Address,on_delete=models.CASCADE)
    contact_person = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    delivery_fee= models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        return self.name
