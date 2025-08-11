import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from orders.models import Order
from course.models import Course, Enrollment
from django.contrib.auth import get_user_model
from .models import PaymentHistory  # Import the PaymentHistory model
import logging

# Get an instance of a logger
logger = logging.getLogger(__name__)

User = get_user_model()

# Stripe API key
stripe.api_key = settings.STRIPE_SECRET_KEY
# Webhook secret from settings
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

@csrf_exempt
def stripe_webhook(request):
    """
    Stripe webhook handler to process payment events.
    """
    logger.info("Stripe webhook received.")
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    if not sig_header:
        logger.warning("Webhook received without Stripe-Signature header.")
        return HttpResponse(status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        logger.info(f"Webhook event constructed successfully. Type: {event['type']}")
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid payload for webhook: {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid signature for webhook: {e}")
        return HttpResponse(status=400)
    except Exception as e:
        # Catch any other unexpected errors during event construction
        logger.error(f"Unexpected error during webhook event construction: {e}")
        return HttpResponse(status=500)


    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        client_reference_id = session.get('client_reference_id')
        session_id = session.get('id')
        logger.info(f"Checkout session completed event. Session ID: {session_id}, Client Reference ID: {client_reference_id}")

        # Retrieve the PaymentHistory record using the Stripe session ID
        payment_history = PaymentHistory.objects.filter(stripe_session_id=session_id).first()
        if not payment_history:
            logger.error(f"Payment history record not found for session ID: {session_id}")
            # It's important to return 200 here so Stripe doesn't keep retrying
            return HttpResponse("Payment history record not found.", status=200)
        
        # Check if the payment status is not already succeeded to prevent double processing
        if payment_history.payment_status == 'succeeded':
            logger.info(f"Payment for session ID {session_id} already processed. Returning 200.")
            return HttpResponse("Payment already processed.", status=200)

        # Update the PaymentHistory record
        payment_history.payment_status = 'succeeded'
        payment_history.save()
        logger.info(f"Payment history for session ID {session_id} updated to 'succeeded'.")


        if client_reference_id and client_reference_id.startswith('order:'):
            order_id = client_reference_id.split(':')[1]
            logger.info(f"Processing order payment for Order ID: {order_id}")
            try:
                order = Order.objects.get(id=order_id)
                order.status = 'paid'
                order.save()
                logger.info(f"Order {order_id} status updated to 'paid'.")
            except Order.DoesNotExist:
                logger.error(f"Order {order_id} not found during webhook processing.")
                return HttpResponse(f"Order {order_id} not found.", status=200) # Return 200 to prevent retries
            except Exception as e:
                logger.error(f"Error updating order {order_id} status: {e}")
                return HttpResponse(f"Error processing order {order_id}.", status=500)

        elif client_reference_id and client_reference_id.startswith('course:'):
            course_id = client_reference_id.split(':')[1]
            logger.info(f"Processing course payment for Course ID: {course_id}")
            try:
                course = Course.objects.get(CourseID=course_id)
                buyer = payment_history.user  # Use the user from the PaymentHistory record
                
                if buyer:
                    enrollment, created = Enrollment.objects.get_or_create(Course=course, EnrolledUser=buyer)
                    if created:
                        logger.info(f"User {buyer.email} successfully enrolled in course {course.CourseID}.")
                    else:
                        logger.info(f"User {buyer.email} was already enrolled in course {course.CourseID}.")
                else:
                    logger.warning(f"Buyer not found in payment history for session ID: {session_id}. Cannot enroll course.")
                    return HttpResponse("Buyer not found.", status=200) # Return 200 to prevent retries

            except Course.DoesNotExist:
                logger.error(f"Course {course_id} not found during webhook processing.")
                return HttpResponse(f"Course {course_id} not found.", status=200) # Return 200 to prevent retries
            except Exception as e:
                logger.error(f"Error enrolling course {course_id} for buyer {buyer.email}: {e}")
                return HttpResponse(f"Error processing course {course_id}.", status=500)
    else:
        logger.info(f"Received webhook event type: {event['type']} (not handled by this function).")

    return HttpResponse(status=200)

