from celery import shared_task
from .services import update_content_based_recommendations

@shared_task
def update_recommendations_task():
    """
    Celery task to update content-based product recommendations.
    """
    print("Starting recommendation update task...")
    update_content_based_recommendations()
    print("Recommendation update task finished.")