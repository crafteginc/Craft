from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings

@shared_task(name="send_formatted_email_task")
def send_formatted_email(subject, body, from_email, recipient_list):
    """
    Asynchronously sends a fully formatted email using EmailMessage.
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
        return f"Email sent successfully to {recipient_list[0]}"
    except Exception as e:
        # Log the error for debugging purposes
        print(f"Failed to send email to {recipient_list[0]}: {e}")
        # You can add more robust logging here if needed
        return f"Failed to send email to {recipient_list[0]}"
