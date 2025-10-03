import random
from django.core.signing import Signer, BadSignature
from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, Customer, Supplier, Delivery, OneTimePassword, Follow
from .utils import Google, send_normal_email

# ✨ NEW: Import the notification service
from notifications.services import create_notification_for_user


def create_user_and_profile(email, first_name, last_name, password, phone_no, user_type, **extra_data):
    """
    Creates a user and their corresponding profile (Customer, Supplier, or Delivery).
    """
    user = User.objects.create_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        PhoneNO=phone_no
    )

    profile_type = ""
    if user_type == "customer":
        Customer.objects.create(user=user)
        user.is_customer = True
        profile_type = "Customer"
    elif user_type == "supplier":
        Supplier.objects.create(
            user=user,
            CategoryTitle=extra_data.get('CategoryTitle'),
            ExperienceYears=extra_data.get('ExperienceYears')
        )
        user.is_supplier = True
        profile_type = "Supplier"
    elif user_type == "delivery":
        Delivery.objects.create(
            user=user,
            plateNO=extra_data.get('plateNO'),
            VehicleModel=extra_data.get('VehicleModel'),
            governorate=extra_data.get('governorate')
        )
        user.is_delivery = True
        profile_type = "Delivery"

    user.save()

    # ✨ NOTIFICATION: Welcome the new user
    create_notification_for_user(
        user=user,
        message=f"Welcome, {user.first_name}! Your {profile_type} profile has been created."
    )
    
    return user


def send_otp_for_user(user, subject, email_template):
    """
    Generates, saves, and sends an OTP to a user for a specific purpose.
    """
    otp = random.randint(1000, 9999)
    OneTimePassword.objects.update_or_create(user=user, defaults={'otp': otp})

    email_context = {
        'subject': subject,
        'user_first_name': user.first_name,
        'otp': otp,
        'recipient_email': user.email
    }
    send_normal_email(template_name=email_template, context=email_context)

    # ✨ NOTIFICATION: Inform the user that an OTP has been sent
    create_notification_for_user(
        user=user,
        message=f"A One-Time Passcode has been sent to your email for: {subject}."
    )


def complete_social_registration(temp_token, phone_no, user_type, **extra_data):
    """
    Finalizes registration for a new social user.
    """
    signer = Signer()
    try:
        social_data = signer.unsign_object(temp_token)
    except BadSignature:
        raise ValidationError("Invalid or expired temporary token.")

    if User.objects.filter(PhoneNO=phone_no).exists():
        raise ValidationError({"error": "Phone number already exists."})

    user = create_user_and_profile(
        email=social_data['email'],
        first_name=social_data['first_name'],
        last_name=social_data['last_name'],
        password=settings.SOCIAL_AUTH_PASSWORD,
        phone_no=phone_no,
        user_type=user_type,
        **extra_data
    )
    user.auth_provider = social_data['provider']
    user.is_verified = True
    user.save()
    
    # ✨ NOTIFICATION: Confirm successful social registration
    create_notification_for_user(
        user=user,
        message="Your account has been successfully created via social login."
    )
    
    return user