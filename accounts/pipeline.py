from django.shortcuts import redirect
from django.core.signing import Signer
from django.conf import settings
from .models import User
from rest_framework_simplejwt.tokens import RefreshToken

signer = Signer()

def create_temp_user(strategy, details, backend, user=None, *args, **kwargs):
    """
    If the user exists, log them in. If they are new, return a temp_token.
    """
    if backend.name in ['google-oauth2', 'facebook']:
        email = details.get("email")
        if not email:
            return redirect('/login/error-no-email/')
        try:
            # Case 1: User already exists (case-insensitive lookup)
            user = User.objects.get(email__iexact=email)
            
            # User exists, so we log them in and provide tokens
            tokens = RefreshToken.for_user(user)
            strategy.session_set("social_data", {
                "is_new": False,
                "email": user.email,
                "first_name": user.first_name,
                "access_token": str(tokens.access_token),
                "refresh_token": str(tokens)
            })

        except User.DoesNotExist:
            # Case 2: New user
            social_data = {
                "email": email,
                "first_name": details.get("first_name", ""),
                "last_name": details.get("last_name", ""),
                "provider": backend.name,
            }
            temp_token = signer.sign_object(social_data)

            # Save it in session for the completion view
            strategy.session_set("social_data", {
                "is_new": True,
                "temp_token": temp_token,
                **social_data
            })
        # Redirect to the JSON response view in both cases
        return redirect('/accounts/social-complete/')