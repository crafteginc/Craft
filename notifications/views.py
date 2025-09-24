from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response
from .models import Notification
from .serializers import NotificationSerializer
from .services import create_notifications_for_all_suppliers,create_notifications_for_all_users

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).select_related('user')

@api_view(['POST'])
@permission_classes([IsAdminUser]) 
def send_to_suppliers_view(request):
    message = request.data.get('message', '')
    if not message:
        return Response(
            {'error': 'Message field is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    create_notifications_for_all_suppliers(message)
    
    return Response(
        {"status": "Notifications have been created and sent to all suppliers."},
        status=status.status.HTTP_201_CREATED
    )

@api_view(['POST'])
@permission_classes([IsAdminUser]) 
def send_to_all_users_view(request):
    """
    An admin-only endpoint to trigger sending notifications to all users.
    """
    message = request.data.get('message', '')
    if not message:
        return Response(
            {'error': 'Message field is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    create_notifications_for_all_users(message)
    
    return Response(
        {"status": "Notifications have been created and sent to all users."},
        status=status.HTTP_201_CREATED
    )