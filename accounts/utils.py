import random
import logging
from django.core.mail import EmailMessage
from django.conf import settings
from .models import User, OneTimePassword
from .tasks import send_formatted_email
from notifications.services import create_notification_for_user

# Get an instance of a logger
logger = logging.getLogger(__name__)

def send_generated_otp_to_email(email, request):
    """
    Generates an OTP and triggers an asynchronous task to send a formatted email.
    Falls back to synchronous sending if the Celery task fails.
    """
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        logger.warning(f"Attempted to send OTP to non-existent user: {email}")
        return

    subject = "One time Passcode for Email Verification"
    otp = random.randint(1000, 9999)
    
    email_body = f"""
    Hi {user.first_name},

    Thanks for signing up on CraftEG! 

    Please verify your email using the following One-Time Passcode (OTP):

    {otp}

    Best regards,  
    The CraftEG Team
    """
    
    from_email = settings.EMAIL_HOST_USER
    OneTimePassword.objects.create(user=user, otp=otp)
    
    try:
        # Asynchronously send the formatted email using the Celery task
        send_formatted_email.delay(
            subject=subject,
            body=email_body,
            from_email=from_email,
            recipient_list=[email]
        )
    except Exception as e:
        # Log the Celery connection error and fall back to synchronous sending
        logger.error(f"Celery task dispatch failed for {email}: {e}. Falling back to synchronous email.", exc_info=True)
        try:
            email_message = EmailMessage(
                subject=subject,
                body=email_body,
                from_email=from_email,
                to=[email]
            )
            email_message.send()
        except Exception as sync_e:
            # Log the failure of the synchronous fallback
            logger.error(f"Synchronous email fallback also failed for {email}: {sync_e}", exc_info=True)

    # Send a notification to the user
    create_notification_for_user(
        user=user,
        message="Your verification passcode has been sent to your email."
    )


def send_normal_email(data):
    """
    A utility function to asynchronously send other types of emails.
    """
    subject = data.get('email_subject', 'No Subject')
    body = data.get('email_body', '')
    recipient = data.get('to_email')

    if not recipient:
        return

    from_email = settings.EMAIL_HOST_USER
    
    # Use the same async task for consistency
    send_formatted_email.delay(
        subject=subject,
        body=body,
        from_email=from_email,
        recipient_list=[recipient]
    )

class Google():
    @staticmethod
    def validate(access_token):
        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token
            
            id_info = id_token.verify_oauth2_token(access_token, google_requests.Request())
            if 'accounts.google.com' in id_info.get('iss', ''):
                return id_info
        except Exception as e:
            logger.error(f"Google token validation error: {e}", exc_info=True)
            return "the token is either invalid or has expired"
