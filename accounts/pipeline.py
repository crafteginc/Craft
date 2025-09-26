from django.shortcuts import redirect
from django.core.signing import Signer
from django.conf import settings

signer = Signer()

def create_temp_user(strategy, details, backend, user=None, *args, **kwargs):
    """
    Stop normal user creation and return a signed temp_token
    with Google profile data.
    """
    if backend.name == 'google-oauth2':
        social_data = {
            "email": details.get("email"),
            "first_name": details.get("first_name", ""),
            "last_name": details.get("last_name", ""),
            "provider": "google",
        }
        temp_token = signer.sign_object(social_data)

        # Save it in session for our custom complete view
        strategy.session_set("social_data", {
            "is_new": True,
            "temp_token": temp_token,
            **social_data
        })

        # Redirect to our new JSON response view
        return redirect('/accounts/google-complete-json/')