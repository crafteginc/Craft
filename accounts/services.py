import random
from django.core.signing import Signer, BadSignature
from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, Customer, Supplier, Delivery, OneTimePassword, Follow
from .utils import Google, send_normal_email


def create_user_and_profile(email, first_name, last_name, password, phone_no, user_type, **extra_data):
    """
    Creates a user and their corresponding profile (Customer, Supplier, or Delivery).
    This single function replaces the save methods in all three registration serializers.
    """
    user = User.objects.create_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        PhoneNO=phone_no
    )

    if user_type == "customer":
        Customer.objects.create(user=user)
        user.is_customer = True
    elif user_type == "supplier":
        Supplier.objects.create(
            user=user,
            CategoryTitle=extra_data.get('CategoryTitle'),
            ExperienceYears=extra_data.get('ExperienceYears')
        )
        user.is_supplier = True
    elif user_type == "delivery":
        Delivery.objects.create(
            user=user,
            plateNO=extra_data.get('plateNO'),
            VehicleModel=extra_data.get('VehicleModel'),
            governorate=extra_data.get('governorate')
        )
        user.is_delivery = True

    user.save()
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
    # This assumes you have an email sending utility that can render templates
    send_normal_email(template_name=email_template, context=email_context)


# --- Social Authentication Services ---

def process_social_login(access_token):
    """
    Validates a Google access token and handles user login or first-time registration.
    Returns a dictionary indicating the user's status and necessary tokens.
    """
    user_data = Google.validate(access_token)
    email = user_data.get('email')
    
    try:
        user = User.objects.get(email=email)
        # Returning user
        tokens = RefreshToken.for_user(user)
        return {
            'is_new_user': False,
            'email': user.email,
            'first_name': user.first_name,
            "access_token": str(tokens.access_token),
            "refresh_token": str(tokens)
        }
    except User.DoesNotExist:
        # New user
        signer = Signer()
        social_data = {
            'email': email,
            'first_name': user_data.get('given_name', ''),
            'last_name': user_data.get('family_name', ''),
            'provider': 'google'
        }
        temp_token = signer.sign_object(social_data)
        return {
            'is_new_user': True,
            'temp_token': temp_token,
            **social_data
        }

def complete_social_registration(temp_token, phone_no, user_type, **extra_data):
    """
    Finalizes registration for a new social user using the temporary token
    and additional profile information.
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
    
    return user