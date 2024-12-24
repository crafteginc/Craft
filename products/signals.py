from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from reviews.models import Review

@receiver(post_save, sender=Review)
def update_product_rating_on_save(sender, instance, **kwargs):
    if instance.product:
        instance.product.update_rating()

@receiver(post_delete, sender=Review)
def update_product_rating_on_delete(sender, instance, **kwargs):
    if instance.product:
        instance.product.update_rating()
