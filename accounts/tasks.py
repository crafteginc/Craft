import logging
from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings

# Get an instance of a logger
logger = logging.getLogger(__name__)

@shared_task(name="send_formatted_email_task")
def send_formatted_email(subject, body, from_email, recipient_list):
    """
    Asynchronously sends a fully formatted email.
    This is a generic task that can be used for any email.
    """
    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=recipient_list
        )
        email.send()
        logger.info(f"Email sent successfully to {recipient_list[0]}")
        return f"Email sent successfully to {recipient_list[0]}"
    except Exception as e:
        # Log the exception for debugging in production
        logger.error(f"Failed to send email to {recipient_list[0]}: {e}", exc_info=True)
        # Re-raise the exception so the task can be marked as failed if needed
        raise


