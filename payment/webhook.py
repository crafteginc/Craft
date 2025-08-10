import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from course.models import Course, Enrollment
from orders.models import Order, User
from returnrequest.models import transactions
from orders.Help import get_craft_user_by_email
from decimal import Decimal
from django.shortcuts import get_object_or_404

stripe.api_key = settings.STRIPE_SECRET_KEY

# Fetch Craft user fresh inside the function to ensure the latest data.

@csrf_exempt
def stripe_webhook(request):
    # Verify Stripe signature and parse event
    payload = request.body
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return HttpResponse(status=400)

    # Only handle checkout.session.completed
    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]

        # Only proceed for mode=payment and payment_status=paid
        if session.get("mode") == "payment" and session.get("payment_status") == "paid":
            client_reference_id = session.get("client_reference_id", "")
            customer_email = session.get("customer_details", {}).get("email") # Use get() with a default to avoid errors

            if not customer_email:
                # No customer email — cannot map to a user
                return HttpResponse(status=400)

            # Fetch Craft (platform) user fresh
            Craft = get_craft_user_by_email("CraftEG@craft.com")
            if not Craft:
                # Platform account missing
                return HttpResponse(status=500)

            # ---------- ORDER PAYMENT ----------
            if isinstance(client_reference_id, str) and client_reference_id.startswith("order:"):
                order_id = client_reference_id.split(":", 1)[1]

                order = get_object_or_404(Order, id=order_id)
                buyer = get_object_or_404(User, email=customer_email)

                try:
                    supplier_user = order.supplier.user
                except Exception:
                    return HttpResponse(status=400)

                fee = (Decimal("0.15") * order.total_amount).quantize(Decimal("0.01"))
                supplier_amount = (order.total_amount - fee).quantize(Decimal("0.01"))

                # Update balances
                supplier_user.Balance = (supplier_user.Balance or Decimal("0.00")) + supplier_amount
                Craft.Balance = (Craft.Balance or Decimal("0.00")) + fee

                # Create transactions
                transactions.objects.create(
                    user=supplier_user,
                    transaction_type=transactions.TransactionType.PURCHASED_PRODUCTS, # Corrected
                    amount=supplier_amount
                )
                transactions.objects.create(
                    user=Craft,
                    transaction_type=transactions.TransactionType.PURCHASED_PRODUCTS,
                    amount=fee
                )

                # Mark order as paid
                order.status = Order.OrderStatus.PAID
                order.stripe_id = session.get("payment_intent") or session.get("id")
                order.save()
                supplier_user.save()
                Craft.save()

                return HttpResponse(status=200)

            # ---------- COURSE PAYMENT ----------
            elif isinstance(client_reference_id, str) and client_reference_id.startswith("course:"):
                course_id = client_reference_id.split(":", 1)[1]

                course = get_object_or_404(Course, CourseID=course_id)
                buyer = get_object_or_404(User, email=customer_email)
                supplier_user = course.Supplier.user

                if buyer == supplier_user:
                    return HttpResponse(status=400)

                if Enrollment.objects.filter(Course=course, EnrolledUser=buyer).exists():
                    return HttpResponse(status=200)

                fee = (Decimal("0.15") * course.Price).quantize(Decimal("0.01"))
                supplier_amount = (course.Price - fee).quantize(Decimal("0.01"))

                supplier_user.Balance = (supplier_user.Balance or Decimal("0.00")) + supplier_amount
                Craft.Balance = (Craft.Balance or Decimal("0.00")) + fee

                transactions.objects.create(
                    user=supplier_user,
                    transaction_type=transactions.TransactionType.PURCHASED_COURSE,
                    amount=supplier_amount
                )
                transactions.objects.create(
                    user=Craft,
                    transaction_type=transactions.TransactionType.PURCHASED_COURSE,
                    amount=fee
                )

                Enrollment.objects.create(Course=course, EnrolledUser=buyer)

                supplier_user.save()
                Craft.save()

                return HttpResponse(status=200)

            # Unknown client_reference_id format
            else:
                return HttpResponse(status=400)

    # For other events or after processing
    return HttpResponse(status=200)