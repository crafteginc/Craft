from django.db.models.signals import post_save
from django.dispatch import Signal, receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification

# 1. Define a custom signal for bulk notifications
notifications_created = Signal()

@receiver(post_save, sender=Notification)
def send_single_notification_on_save(sender, instance, created, **kwargs):
    """
    Handles sending a single notification when it's created normally.
    This remains for cases where you create one notification at a time.
    """
    if created:
        channel_layer = get_channel_layer()
        group_name = f"user_{instance.user.id}"
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'send_notification',
                'message': instance.message,
            }
        )

@receiver(notifications_created)
def send_bulk_notifications(sender, notifications, **kwargs):
    """
    Handles sending bulk notifications after they have been created.
    This receiver listens to our custom signal.
    """
    channel_layer = get_channel_layer()
    for notification in notifications:
        group_name = f"user_{notification.user.id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'send_notification',
                'message': notification.message,
            }
        )