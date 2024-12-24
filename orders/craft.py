from accounts.models import User
def get_craft_user_by_email(email):
    try:
        # Attempting to get the user by email
        return User.objects.get(email=email)
    except User.DoesNotExist:
        # Return None if no user is found
        return None
    except Exception as e:
        # Handle any other potential errors
        print(f"Error occurred: {e}")
        return None