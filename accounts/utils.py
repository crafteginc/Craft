import random
from django.conf import settings
from django.core.mail import EmailMessage
from .models import User, OneTimePassword
from .tasks import send_formatted_email
from notifications.services import create_notification_for_user


def send_generated_otp_to_email(email, request):
    """
    Generate and send OTP to the user's email.
    Uses Celery + Resend API (if configured), otherwise falls back to Django Email.
    """
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return

    # Generate a 4-digit OTP
    otp = random.randint(1000, 9999)
    OneTimePassword.objects.create(user=user, otp=otp)

    subject = "One-Time Passcode for Email Verification"
    email_body = f"""
    Hi {user.first_name},

    Thanks for signing up on CraftEG!

    Please verify your email using the following One-Time Passcode (OTP):

    {otp}

    Best regards,  
    The CraftEG Team
    """

    from_email = settings.DEFAULT_FROM_EMAIL

    try:
        # Try sending asynchronously via Celery + Resend
        send_formatted_email.delay(
            subject=subject,
            body=email_body,
            from_email=from_email,
            recipient_list=email
        )
    except Exception as e:
        print(f"⚠️ Celery or Resend failed, using fallback SMTP. Reason: {e}")
        # Fallback to direct Django email
        email_message = EmailMessage(
            subject=subject,
            body=email_body,
            from_email=from_email,
            to=[email]
        )
        email_message.send(fail_silently=False)

    # Create an in-app notification
    create_notification_for_user(
        user=user,
        message="Your verification passcode has been sent to your email."
    )


def send_normal_email(data):
    """
    Send a general-purpose email (notifications, updates, etc.).
    """
    subject = data.get('email_subject', 'No Subject')
    body = data.get('email_body', '')
    recipient = data.get('to_email')

    if not recipient:
        print("⚠️ Email recipient not provided.")
        return

    from_email = settings.DEFAULT_FROM_EMAIL

    try:
        send_formatted_email.delay(
            subject=subject,
            body=body,
            from_email=from_email,
            recipient_list=recipient
        )
    except Exception as e:
        print(f"⚠️ Celery or Resend failed, fallback to SMTP. Reason: {e}")
        email_message = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[recipient]
        )
        email_message.send(fail_silently=False)


class Google:
    """
    Helper class for verifying Google OAuth2 tokens.
    """
    @staticmethod
    def validate(access_token):
        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token

            id_info = id_token.verify_oauth2_token(
                access_token, google_requests.Request()
            )
            if 'accounts.google.com' in id_info.get('iss', ''):
                return id_info
        except Exception:
            return "The token is either invalid or has expired"
