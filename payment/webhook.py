import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from orders.models import Order
from course.models import Course, Enrollment
from django.contrib.auth import get_user_model
from .models import PaymentHistory

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
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)
    except Exception as e:
        # Catch any other unexpected errors during event construction
        return HttpResponse(status=500)


    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        client_reference_id = session.get('client_reference_id')
        session_id = session.get('id')
        payment_intent_id = session.get('payment_intent')
        
        payment_history = PaymentHistory.objects.filter(stripe_session_id=session_id).first()
        if not payment_history:
            return HttpResponse("Payment history record not found.", status=200)
        
        if payment_history.payment_status == 'succeeded':
            return HttpResponse("Payment already processed.", status=200)

        payment_history.payment_status = 'succeeded'
        payment_history.stripe_payment_intent_id = payment_intent_id
        payment_history.save()

        if client_reference_id and client_reference_id.startswith('order:'):
            order_id = client_reference_id.split(':')[1]
            try:
                order = Order.objects.get(id=order_id)
                order.paid = True
                order.save()
            except Order.DoesNotExist:
                return HttpResponse(f"Order {order_id} not found.", status=200)
            except Exception as e:
                return HttpResponse(f"Error processing order {order_id}.", status=500)

        elif client_reference_id and client_reference_id.startswith('course:'):
            course_id = client_reference_id.split(':')[1]
            try:
                course = Course.objects.get(CourseID=course_id)
                buyer = payment_history.user
                
                if buyer:
                    enrollment, created = Enrollment.objects.get_or_create(Course=course, EnrolledUser=buyer)
                else:
                    return HttpResponse("Buyer not found.", status=200)

            except Course.DoesNotExist:
                return HttpResponse(f"Course {course_id} not found.", status=200)
            except Exception as e:
                return HttpResponse(f"Error enrolling course {course_id} for buyer {buyer.email}: {e}")
    
    return HttpResponse(status=200)

