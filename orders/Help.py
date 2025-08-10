from accounts.models import User
from rest_framework.exceptions import ValidationError
from .models import Warehouse

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
    
def get_warehouse_by_name(state_name):
    try:
        return Warehouse.objects.get(name=state_name)
    except Warehouse.DoesNotExist:
        raise ValidationError(f"Warehouse not found for state: {state_name}")