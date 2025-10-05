from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    image = models.ImageField(upload_to='notifications/%Y/%m/%d/', null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    # Generic foreign key to link to any object (e.g., a ReturnRequest or an Order)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=36, null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return self.message

    class Meta:
        ordering = ("-timestamp",)

    @property
    def image_url(self):
        """
        Returns the URL of the image if it exists, otherwise None.
        """
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        return None