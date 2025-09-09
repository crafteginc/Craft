from django.db import models
from accounts.models import User,Address
from orders.models import Order, Cart
from course.models import Course, Enrollment
import uuid

class PaymentHistory(models.Model):
    """
    Model to log payment attempts and their status.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="The user who initiated the payment."
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="The associated order for the payment, if any."
    )
    cart = models.ForeignKey(
        Cart,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="The associated cart for the payment."
    )
    address_id= models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="The address used for the order."
    )
    coupon_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="The coupon code used for the order."
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="The associated course for the payment, if any."
    )
    stripe_session_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="The ID of the Stripe checkout session."
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="The ID of the Stripe Payment Intent associated with the transaction."
    )
    date = models.DateTimeField(
        auto_now_add=True,
        help_text="The date and time the payment record was created."
    )
    payment_status = models.CharField(
        max_length=50,
        default='pending',
        choices=[('pending', 'Pending'), ('succeeded', 'Succeeded'), ('failed', 'Failed')],
        help_text="The status of the payment (e.g., pending, succeeded, failed)."
    )

    class Meta:
        verbose_name_plural = "Payment Histories"

    def __str__(self):
        if self.order:
            return f"Payment for Order {self.order.id} - {self.payment_status}"
        elif self.course:
            return f"Payment for Course {self.course.CourseID} - {self.payment_status}"
        return f"Payment by {self.user.email} - {self.payment_status}"