from decimal import Decimal
import stripe
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from orders.models import Cart, CartItems
from course.models import Course, Enrollment
from .serializers import CourseInformationSerializer
from .models import PaymentHistory
from orders.services import _calculate_all_order_totals_helper
from accounts.models import Address

# Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentViewSet(viewsets.ViewSet):
    """
    Handles payment processing for Orders.
    """

    @action(detail=False, methods=["post"])
    def process_order_payment(self, request):
        user = request.user
        cart = get_object_or_404(Cart, User=user)
        address_id = request.data.get("address_id")
        coupon_code = request.data.get("coupon_code")

        # Retrieve the Address instance using the ID
        try:
            address = Address.objects.get(user=user, id=address_id)
        except Address.DoesNotExist:
            raise ValidationError("Address not found or does not belong to the user.")

        cart_items = CartItems.objects.filter(CartID=cart)

        if not cart_items.exists():
            raise ValidationError({"message": "Cart is empty. Cannot create order."})

        # Calculate totals using the helper function
        totals = _calculate_all_order_totals_helper(cart_items, coupon_code, address, user)

        # Create a pending PaymentHistory record before creating the session
        payment_history = PaymentHistory.objects.create(
            user=user,
            cart=cart,
            payment_status='pending',
            address_id=address,
            coupon_code=coupon_code,
        )

        base_success_url = request.build_absolute_uri(reverse("payment:success"))
        success_url = f"{base_success_url}?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = request.build_absolute_uri(reverse("payment:cancel"))

        session_data = {
            "mode": "payment",
            "client_reference_id": str(payment_history.id),
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items": [],
        }

        delivery_fee = totals['delivery_fee'] if totals['delivery_fee'] else Decimal("0.00")
        sub_total_amount = totals['total_amount'] - totals['discount_amount']
        
        if sub_total_amount > 0:
            session_data["line_items"].append(
                {
                    "price_data": {
                        "unit_amount": int(sub_total_amount * Decimal("100")),
                        "currency": "EGP",
                        "product_data": {
                            "name": "Order Items",
                        },
                    },
                    "quantity": 1,
                }
            )

        if delivery_fee > 0:
            session_data["line_items"].append(
                {
                    "price_data": {
                        "unit_amount": int(delivery_fee * Decimal("100")),
                        "currency": "EGP",
                        "product_data": {
                            "name": "Delivery Fee",
                        },
                    },
                    "quantity": 1,
                }
            )
        
        try:
            session = stripe.checkout.Session.create(**session_data)
            payment_history.stripe_session_id = session.id
            payment_history.save()
            return Response({"status": "success", "url": session.url})
        except stripe.error.StripeError as e:
            payment_history.payment_status = 'failed'
            payment_history.save()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CoursePaymentViewSet(viewsets.ViewSet):
    """
    Handles payment processing for Courses.
    """

    @action(detail=False, methods=["post"])
    def process_course_payment(self, request):
        serializer = CourseInformationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course_id = serializer.validated_data["course_id"]
        course = get_object_or_404(Course, CourseID=course_id)
        
        buyer = request.user
        
        if buyer == course.Supplier.user:
            return Response({"error": "You cannot purchase your own course."}, status=status.HTTP_400_BAD_REQUEST)

        if Enrollment.objects.filter(Course=course, EnrolledUser=buyer).exists():
            return Response({"error": "You are already enrolled in this course."}, status=status.HTTP_400_BAD_REQUEST)

        payment_history = PaymentHistory.objects.create(
            user=buyer,
            course=course,
            payment_status='pending'
        )

        base_success_url = request.build_absolute_uri(reverse("payment:success"))
        success_url = f"{base_success_url}?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = request.build_absolute_uri(reverse("payment:cancel"))

        session_data = {
            "mode": "payment",
            "client_reference_id": f"course:{course.CourseID}",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items": [{
                "price_data": {
                    "unit_amount": int(course.Price * Decimal("100")),
                    "currency": "EGP",
                    "product_data": {
                        "name": course.CourseTitle,
                    },
                },
                "quantity": 1,
            }],
        }
        
        try:
            session = stripe.checkout.Session.create(**session_data)
            payment_history.stripe_session_id = session.id
            payment_history.save()
            return Response({"status": "success", "url": session.url})
        except stripe.error.StripeError as e:
            payment_history.payment_status = 'failed'
            payment_history.save()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
def payment_completed(request):
    """
    Endpoint for successful payment redirect.
    Renders a success page for the user.
    """
    session_id = request.GET.get('session_id')
    context = {
        "status": "success",
        "message": "Payment Successful!",
        "session_id": session_id
    }
    return render(request, 'payment/payment_result.html', context)

@api_view(['GET'])
def payment_canceled(request):
    """
    Endpoint for canceled payment redirect.
    Renders a failure page for the user.
    """
    context = {
        "status": "failed",
        "message": "Payment Canceled",
        "session_id": None
    }
    return render(request, 'payment/payment_result.html', context)