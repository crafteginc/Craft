import random
import asyncio
from django.core.mail import EmailMessage
from django.conf import settings
from .models import User, OneTimePassword

# دالة غير متزامنة لإرسال OTP عبر البريد الإلكتروني
async def send_generated_otp_to_email(email, request):
    subject = "One time Passcode for Email Verification"
    otp = random.randint(1000, 9999)
    
    # جلب المستخدم بشكل غير متزامن
    user = await asyncio.to_thread(User.objects.get, email=email)
    
    email_body = f"""
    Hi {user.first_name},

    Thanks for signing up on CraftEG! 

    Please verify your email using the following One-Time Passcode (OTP): 
    {otp}

    Best regards,  
    The CraftEG Team
    """
    from_email = settings.EMAIL_HOST_USER
    
    # إنشاء كائن OTP في قاعدة البيانات بشكل غير متزامن
    await asyncio.to_thread(OneTimePassword.objects.create, user=user, otp=otp)
    
    # إرسال البريد الإلكتروني بشكل غير متزامن
    d_email = EmailMessage(subject=subject, body=email_body, from_email=from_email, to=[user.email])
    await asyncio.to_thread(d_email.send)

# دالة لإرسال بريد إلكتروني عادي بشكل غير متزامن
async def send_normal_email(data):
    email = EmailMessage(
        subject=data['email_subject'],
        body=data['email_body'],
        from_email=settings.EMAIL_HOST_USER,
        to=[data['to_email']]
    )
    await asyncio.to_thread(email.send)


# class Google():
#     @staticmethod
#     def validate(access_token):
#         try:
#             id_info=id_token.verify_oauth2_token(access_token, requests.Request())
#             if 'accounts.google.com' in id_info['iss']:
#                 return id_info
#         except:
#             return "the token is either invalid or has expired"

# def register_social_user(provider, email, first_name, last_name):
#     old_user=User.objects.filter(email=email)
#     if old_user.exists():
#         if provider == old_user[0].auth_provider:
#             register_user=authenticate(email=email, password=settings.SOCIAL_AUTH_PASSWORD)

#             return {
#                 'full_name':register_user.get_full_name,
#                 'email':register_user.email,
#                 'tokens':register_user.tokens()
#             }
#         else:
#             raise AuthenticationFailed(
#                 detail=f"please continue your login with {old_user[0].auth_provider}"
#             )
#     else:
#         new_user={
#             'email':email,
#             'first_name':first_name,
#             'last_name':last_name,
#             'password':settings.SOCIAL_AUTH_PASSWORD
#         }
#         user=User.objects.create_user(**new_user)
#         user.auth_provider=provider
#         user.is_verified=True
#         user.save()
#         login_user=authenticate(email=email, password=settings.SOCIAL_AUTH_PASSWORD)
       
#         tokens=login_user.tokens()
#         return {
#             'email':login_user.email,
#             'full_name':login_user.get_full_name,
#             "access_token":str(tokens.get('access')),
#             "refresh_token":str(tokens.get('refresh'))
#         }

