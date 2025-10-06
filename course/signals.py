from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from reviews.models import Review
from .tasks import update_course_rating_task


@receiver(post_save, sender=Review)
def update_course_rating_on_save(sender, instance, **kwargs):
    if instance.course:
        # ✨ Offload rating calculation to Celery
        update_course_rating_task.delay(instance.course.id)


@receiver(post_delete, sender=Review)
def update_course_rating_on_delete(sender, instance, **kwargs):
    if instance.course:
        # ✨ Offload rating calculation to Celery
        update_course_rating_task.delay(instance.course.id)