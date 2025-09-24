from .models import Notification
from accounts.models import User
from .signals import notifications_created # Import our custom signal

def create_notification_for_user(user, message):
    """
    Creates a single notification. The 'post_save' signal will handle sending it.
    """
    Notification.objects.create(user=user, message=message)


def create_notifications_for_all_suppliers(message):
    """
    Finds all supplier users and creates notifications for them in a single,
    efficient database query, then fires a single signal to send them all.
    """
    suppliers = User.objects.filter(is_supplier=True)
    if not suppliers:
        return

    # 1. Prepare all Notification objects in memory
    notifications_to_create = [
        Notification(user=supplier, message=message) for supplier in suppliers
    ]
    
    # 2. Insert all of them into the database in one query
    created_notifications = Notification.objects.bulk_create(notifications_to_create)

    # 3. Send our custom signal with the list of newly created notifications
    notifications_created.send(sender=None, notifications=created_notifications)

def create_notifications_for_all_users(message):
    """
    Creates a notification for every user in the system in a single bulk query.
    """
    all_users = User.objects.all()
    if not all_users:
        return

    # 1. Prepare all Notification objects in memory
    notifications_to_create = [
        Notification(user=user, message=message) for user in all_users
    ]
    
    # 2. Insert all of them into the database in one query
    created_notifications = Notification.objects.bulk_create(notifications_to_create)

    # 3. Send our custom signal to broadcast them via WebSocket
    notifications_created.send(sender=None, notifications=created_notifications)
