from rest_framework.permissions import BasePermission

class IsReturnRequestOwner(BasePermission):
    """
    Allows access only to the user who created the return request.
    """
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user

class IsAssignedDeliveryPerson(BasePermission):
    """
    Allows access only to the delivery person assigned to the request.
    """
    def has_object_permission(self, request, view, obj):
        return hasattr(request.user, 'delivery') and obj.delivery_person == request.user.delivery

class IsRequestSupplier(BasePermission):
    """

    Allows access only to the supplier associated with the return request.
    """
    def has_object_permission(self, request, view, obj):
        return hasattr(request.user, 'supplier') and obj.supplier == request.user.supplier