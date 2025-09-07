from rest_framework import permissions
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework.exceptions import ValidationError
from accounts.models import Address
class IsSupplier(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and hasattr(request.user, 'supplier')

class SupplierContractProvided(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if user.is_authenticated and hasattr(user, 'supplier'):
            supplier = user.supplier
            if not supplier.SupplierContract and not supplier.SupplierIdentity:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"user_{request.user.id}",
                    {
                        "type": "send_notification",
                        "message": "Upload your contract and identity documents, please."
                    }
                )
                return False
            
            # Check if the supplier is marked as accepted
            if not supplier.accepted_supplier:
                raise ValidationError("Your supplier account has not been accepted yet.the adminstrators will accept your documents soon ")
            
        return True

class DeliveryContractProvided(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if user.is_authenticated and hasattr(user, 'delivery'):
            delivery = user.delivery
            if not delivery.DeliveryContract and not delivery.DeliveryIdentity:
             channel_layer = get_channel_layer()
             async_to_sync(channel_layer.group_send)(
              f"user_{request.user.id}",
              {
              "type": "send_notification",
             "message": "upload your contract please ."
               }
               )
             return False
         # Check if the supplier is marked as accepted
            if not delivery.accepted_delivery:
                raise ValidationError("Your delivery account has not been accepted yet.the adminstrators will accept your documents soon ")
            
        return True

class SupplierHasAddress(permissions.BasePermission):
    def has_permission(self, request, view):
        # This permission only applies to the 'create' action for a POST request.
        if view.action == 'create':
            user = request.user
            # A supplier can add a product only if they have at least one address associated with their user account.
            if hasattr(user, 'supplier') and Address.objects.filter(user=user).exists():
                return True
            raise ValidationError("You must provide a business address before adding a product.")
        # All other actions are allowed.
        return True
