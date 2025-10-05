from celery import shared_task
from django.core.mail import EmailMessage


@shared_task(name="send_formatted_email_task")
def send_formatted_email(subject, body, from_email, recipient_list):
    """
    Send an email safely through Celery.
    Handles both string and list recipients.
    """
    # Convert to a proper list (cleanly handle weird Celery serialization)
    if isinstance(recipient_list, str):
        # Remove extra brackets or quotes if any
        recipient_list = recipient_list.strip("[]'\" ")
        recipient_list = [recipient_list]
    elif not isinstance(recipient_list, list):
        recipient_list = [str(recipient_list)]

    email_message = EmailMessage(
        subject=subject,
        body=body,
        from_email=from_email,
        to=recipient_list
    )

    email_message.send()
    return f"Email sent successfully to {recipient_list}"
