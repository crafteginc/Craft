import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from orders.models import Order
from orders.services import create_order_from_cart
from course.models import Course, Enrollment
from django.contrib.auth import get_user_model
from .models import PaymentHistory
from django.db import transaction
from notifications.services import create_notification_for_user

User = get_user_model()

stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    if not sig_header:
        return HttpResponse(status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)
    except Exception as e:
        return HttpResponse(status=500)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        client_reference_id = session.get('client_reference_id')
        session_id = session.get('id')
        payment_intent_id = session.get('payment_intent')
        
        try:
            payment_history_id = client_reference_id
            payment_history = PaymentHistory.objects.get(id=payment_history_id)
        except (PaymentHistory.DoesNotExist, ValueError):
            if client_reference_id and client_reference_id.startswith('course:'):
                course_id = client_reference_id.split(':')[1]
                try:
                    payment_history = PaymentHistory.objects.get(stripe_session_id=session_id)
                    course = payment_history.course
                    buyer = payment_history.user
                    if buyer:
                        enrollment, created = Enrollment.objects.get_or_create(Course=course, EnrolledUser=buyer)
                        if created:
                            # ✨ NOTIFICATION: Inform user of successful enrollment
                            create_notification_for_user(
                                user=buyer,
                                message=f"You have successfully enrolled in the course: {course.CourseTitle}",
                                related_object=course,
                                image=course.Thumbnail
                            )
                except (PaymentHistory.DoesNotExist, Course.DoesNotExist, Exception) as e:
                    return HttpResponse(f"Error processing course payment: {e}", status=200)
                return HttpResponse(status=200)
            
            return HttpResponse("Client reference ID does not match a valid payment history record.", status=200)

        with transaction.atomic():
            if payment_history.payment_status == 'succeeded':
                return HttpResponse("Payment already processed.", status=200)

            payment_history.payment_status = 'succeeded'
            payment_history.stripe_payment_intent_id = payment_intent_id
            payment_history.save()

            user = payment_history.user
            cart = payment_history.cart
            address_object = payment_history.address_id
            coupon_code = payment_history.coupon_code
            
            order = create_order_from_cart(user, cart, address_object.id, coupon_code, Order.PaymentMethod.CREDIT_CARD, is_paid=True)
            
            payment_history.order = order
            payment_history.save()
            
            # ✨ NOTIFICATION: Inform user of successful payment
            create_notification_for_user(
                user=user,
                message=f"Your payment for order #{order.order_number} was successful.",
                related_object=order
            )
            
            return HttpResponse(status=200)

    return HttpResponse(status=200)