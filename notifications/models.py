from django.db import models
from accounts.models import User

class NotificationManager(models.Manager):
    def create_and_send(self, user, message):
        """
        Creates a notification and prepares it to be sent.
        The actual sending logic will be handled by a service.
        """
        notification = self.create(user=user, message=message)
        # In a more advanced system, you might trigger a signal here
        # or pass this object directly to a sending service.
        return notification

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    objects = NotificationManager()

    def __str__(self):
        return self.message

    class Meta:
        ordering = ("-timestamp",)