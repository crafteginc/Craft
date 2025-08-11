from decimal import Decimal
import stripe
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from orders.models import Order
from course.models import Course, Enrollment
from .serializers import OrderInformationSerializer, CourseInformationSerializer
from .models import PaymentHistory  # Import the new model

# Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY

class PaymentViewSet(viewsets.ViewSet):
    """
    Handles payment processing for Orders.
    """

    @action(detail=False, methods=["post"])
    def process_order_payment(self, request):
        serializer = OrderInformationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order_id = serializer.validated_data["order_id"]
        order = get_object_or_404(Order, id=order_id)

        # Create a pending PaymentHistory record before creating the session
        payment_history = PaymentHistory.objects.create(
            user=request.user,
            order=order,
            payment_status='pending'
        )
        
        # FIX: Construct the base URL first, then append the unencoded placeholder
        base_success_url = request.build_absolute_uri(reverse("payment:success"))
        success_url = f"{base_success_url}?session_id={{CHECKOUT_SESSION_ID}}"
        
        cancel_url = request.build_absolute_uri(reverse("payment:cancel"))

        session_data = {
            "mode": "payment",
            "client_reference_id": f"order:{order.id}",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "line_items": [],
        }

        # Add line items for the order
        for item in order.items.all():
            session_data["line_items"].append(
                {
                    "price_data": {
                        "unit_amount": int(item.price * Decimal("100")),
                        "currency": "EGP",
                        "product_data": {
                            "name": item.product.ProductName,
                        },
                    },
                    "quantity": item.quantity,
                }
            )

        delivery_fee = order.delivery_fee if order.delivery_fee else Decimal("0.00")
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
            # Update the payment history with the session ID
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

        # Create a pending PaymentHistory record
        payment_history = PaymentHistory.objects.create(
            user=buyer,
            course=course,
            payment_status='pending'
        )

        # FIX: Construct the base URL first, then append the unencoded placeholder
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
            # Update the payment history with the session ID
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
    It's recommended to handle post-payment logic in the webhook.
    """
    session_id = request.GET.get('session_id')
    if not session_id:
        return Response("Session ID not provided.", status=status.HTTP_400_BAD_REQUEST)

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        # You can retrieve details here, but the webhook is the source of truth.
        return Response({
            "message": "Payment accepted, processing...",
            "session_id": session.id
        }, status=status.HTTP_202_ACCEPTED)
    except stripe.error.StripeError:
        return Response("Invalid session ID.", status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def payment_canceled(request):
    """
    Endpoint for canceled payment redirect.
    """
    return Response(
        {"message": "Your payment was canceled."}, 
        status=status.HTTP_406_NOT_ACCEPTABLE
    )
