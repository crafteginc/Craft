import random
import asyncio
from django.core.mail import EmailMessage
from django.conf import settings
import requests
from .models import User, OneTimePassword
import requests
from google.auth.transport import requests
from google.oauth2 import id_token
from accounts.models import User
from django.contrib.auth import authenticate
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from notifications.services import create_notification_for_user


def send_generated_otp_to_email(email, request):
    subject = "One time Passcode for Email Verification"
    otp = random.randint(1000, 9999)
    user = User.objects.get(email=email) 
    email_body = f"""
Hi {user.first_name},

Thank you for signing up with CraftEG!

To verify your email address, please use the following One-Time Passcode (OTP):

👉 {otp}

If you didn’t request this, please ignore this message.

Best regards,  
The CraftEG Team  
"""
    from_email = settings.DEFAULT_FROM_EMAIL
    OneTimePassword.objects.create(user=user, otp=otp)
    d_email = EmailMessage(subject=subject, body=email_body, from_email=from_email, to=[user.email])
    d_email.send()

    # ✨ NOTIFICATION: Inform the user that an OTP has been sent
    create_notification_for_user(
        user=user,
        message="Your verification passcode has been sent to your email."
    )


def send_normal_email(data):
    email = EmailMessage(
        subject=data['email_subject'],
        body=data['email_body'],
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[data['to_email']]
    )
    email.send()

class Google():
    @staticmethod
    def validate(access_token):
        try:
            id_info=id_token.verify_oauth2_token(access_token, requests.Request())
            if 'accounts.google.com' in id_info['iss']:
                return id_info
        except:
            return "the token is either invalid or has expired"