import resend
from celery import shared_task
from django.conf import settings

resend.api_key = settings.RESEND_API_KEY


@shared_task(name="send_formatted_email_task")
def send_formatted_email(subject, body, from_email, recipient_list):
    try:
        if isinstance(recipient_list, str):
            recipient_list = [recipient_list]

        for recipient in recipient_list:
            resend.Emails.send({
                "from": from_email,
                "to": recipient,
                "subject": subject,
                "text": body,
            })
        print(f"✅ Email sent successfully to {recipient_list}")
        return f"Email sent successfully to {recipient_list}"
    except Exception as e:
        print(f"❌ Email sending failed: {str(e)}")
        raise e
