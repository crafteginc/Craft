import random
from django.core.mail import EmailMessage
from django.conf import settings
import requests
from .models import User, OneTimePassword
import requests
from google.auth.transport import requests
from google.oauth2 import id_token
from accounts.models import User
from .tasks import send_otp_email
from django.conf import settings
from notifications.services import create_notification_for_user


def send_generated_otp_to_email(email, request):
    user = User.objects.get(email=email)
    otp = random.randint(1000, 9999)
    OneTimePassword.objects.create(user=user, otp=otp)

    # Pass the otp to the celery task
    send_otp_email.delay(email, otp)

    # ✨ NOTIFICATION: Inform the user that an OTP has been sent
    create_notification_for_user(
        user=user,
        message="Your verification passcode has been sent to your email."
    )


def send_normal_email(data):
    email = EmailMessage(
        subject=data['email_subject'],
        body=data['email_body'],
        from_email=settings.EMAIL_HOST_USER,
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