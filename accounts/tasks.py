from celery import shared_task
from django.core.mail import EmailMessage


@shared_task(name="send_formatted_email_task")
def send_formatted_email(subject, body, from_email, recipient_list):
    try:
        if isinstance(recipient_list, str):
            recipient_list = [recipient_list]

        email_message = EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email,
            to=recipient_list
        )
        email_message.send(fail_silently=False)
        print(f"✅ Email sent successfully to {recipient_list}")
        return f"Email sent successfully to {recipient_list}"
    except Exception as e:
        print(f"❌ Email sending failed: {str(e)}")
        raise e