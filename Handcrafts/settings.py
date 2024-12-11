import os 
import dj_database_url
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start  settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-_qypz^00_)q5$=i_16^5k#f5)w67#s12_i8x9zlhn5mwt15k&h'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['*', 'http://localhost:3000']


# Application definition

INSTALLED_APPS = [
    'admin_interface',
    'colorfield',
    'daphne',
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'products',
    'course',
    'orders',
    'reviews',
    'rest_framework_swagger', 
    'drf_yasg',
    'payment',
    'notifications',
    'chatapp',
    'returnrequest',
    #third party packages
    'rest_framework',
    'django_filters',
    'rest_framework_simplejwt.token_blacklist',


    #social authentication
]

#STRIPE
STRIPE_SECRET_KEY = 'sk_test_51PVhW3Ruzd5caPY0sQvASyRNQw2fZG9S333H7oYl6R3QuYWHFNzGkxakPwLGleb16DSNN1mxcniLbDg21rJeonT800OikLGNqw'
STRIPE_PUBLISHABLE_KEY = 'pk_test_51PVhW3Ruzd5caPY0S3XDtAv51PxSu2nSYCLVL2C168LOVJ5U3z73hxOkD0GoeIodJtOZFTdlt6ghqa0NlC6AtI7l00YJyGdekj'
STRIPE_WEBHOOK_SECRET = 'whsec_67f96b05e1a4377a27a49a3b932b3b130e6fd523c9dc03e02a37caf5bed6cdba'

GOOGLE_CLIENT_ID="538228859657-u8el2po0kiefkggrsi4gtog6jrdj91do.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="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"
SOCIAL_AUTH_PASSWORD="12345678"

EMAIL_HOST = 'sandbox.smtp.mailtrap.io'
EMAIL_HOST_USER = 'b41f95b7a394e2'
EMAIL_HOST_PASSWORD = '73ae604151780f'
EMAIL_PORT = '587'

SOCIAL_AUTH_FACEBOOK_KEY = '770235291829528'
SOCIAL_AUTH_FACEBOOK_SECRET = '30cc0836c451f2ead4d8e7ec90a1e564'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    )
}

# SOCIAL_AUTH_FACEBOOK_KEY = '1118977622571710'
# SOCIAL_AUTH_FACEBOOK_SECRET = '7e66d9629e33c83abb49ecbe2e8cd35d'
# # Define SOCIAL_AUTH_FACEBOOK_SCOPE to get extra permissions from Facebook.
# # Email is not sent by default, to get it, you must request the email permission.
# SOCIAL_AUTH_FACEBOOK_SCOPE = ['email']
# SOCIAL_AUTH_FACEBOOK_PROFILE_EXTRA_PARAMS = {
#    'fields': 'id, name, email'

# CORS_ALLOWED_ORIGINS = [
#    "http://localhost:3000",
#    "http://127.0.0.1:3000"
# ]

SIMPLE_JWT = {# third party 
    'ACCESS_TOKEN_LIFETIME': timedelta(days=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'BLACKLIST_AFTER_ROTATION':True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    #'UPDATE_LAST_LOGIN':True,
}

AUTH_USER_MODEL = 'accounts.User'


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "corsheaders.middleware.CorsMiddleware",

]
ROOT_URLCONF = 'Handcrafts.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                    #aditional for allowed the frontend login

                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
            ],
        },
    },
]

ALLOWED_HOSTS = ["*"]

WSGI_APPLICATION = 'Handcrafts.wsgi.application'

ASGI_APPLICATION = 'Handcrafts.asgi.application'

#this can be used in Production
# CHANNEL_LAYERS = {
#     'default': {
#         'BACKEND': 'channels_redis.core.RedisChannelLayer',
#         'CONFIG': {
#             "hosts": [('127.0.0.1', 6379)],
#         },
#     },
# }

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': dj_database_url.config(default=os.getenv('postgresql://postgres:NXDGelQcZNBmSVsfEPHpgwAQZMKoLBOe@junction.proxy.rlwy.net:58374/railway'))
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'
# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
