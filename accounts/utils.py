import random
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from .models import User, OneTimePassword
from .tasks import send_formatted_email # Updated import
from notifications.services import create_notification_for_user


def send_generated_otp_to_email(email, request):
    """
    Generates an OTP, saves it, and triggers an asynchronous task to send a formatted email.
    Falls back to synchronous sending if the task fails.
    """
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        print(f"Attempted to send OTP to non-existent user: {email}")
        return

    subject = "One time Passcode for Email Verification"
    otp = random.randint(1000, 9999)
    
    # Create the rich, user-friendly email body
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
        # Asynchronously send the FULLY FORMATTED email using the updated Celery task
        send_formatted_email.delay(
            subject=subject,
            body=email_body,
            from_email=from_email,
            recipient_list=[email]
        )
        print(f"Celery task dispatched to send OTP to {email}")

    except Exception as e:
        # Log the error and fall back to synchronous email sending with the SAME formatted email
        print(f"Celery task failed for {email}: {e}. Falling back to synchronous email.")
        try:
            email_message = EmailMessage(
                subject=subject,
                body=email_body,
                from_email=from_email,
                to=[email]
            )
            email_message.send()
        except Exception as sync_e:
            print(f"Synchronous email fallback also failed for {email}: {sync_e}")

    # Send the notification regardless of email success
    create_notification_for_user(
        user=user,
        message="Your verification passcode has been sent to your email."
    )


def send_normal_email(data):
    """
    A utility function to send other types of emails, can also be converted to use the async task.
    """
    subject = data.get('email_subject', 'No Subject')
    body = data.get('email_body', '')
    recipient = data.get('to_email')

    if not recipient:
        return

    from_email = settings.EMAIL_HOST_USER
    
    # You can use the same async task here for consistency!
    send_formatted_email.delay(
        subject=subject,
        body=body,
        from_email=from_email,
        recipient_list=[recipient]
    )


class Google():
    @staticmethod
    def validate(access_token):
        # This part is unchanged
        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token
            
            id_info = id_token.verify_oauth2_token(access_token, google_requests.Request())
            if 'accounts.google.com' in id_info.get('iss', ''):
                return id_info
        except Exception as e:
            print(f"Google token validation error: {e}")
            return "the token is either invalid or has expired"
