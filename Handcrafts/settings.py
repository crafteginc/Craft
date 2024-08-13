import os 
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start  settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-_qypz^00_)q5$=i_16^5k#f5)w67#s12_i8x9zlhn5mwt15k&h'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

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
STRIPE_SECRET_KEY = #use your KEY
STRIPE_PUBLISHABLE_KEY = #use your KEY
STRIPE_WEBHOOK_SECRET = #use your KEY

GOOGLE_CLIENT_ID= #use your KEY
GOOGLE_CLIENT_SECRET=#use your KEY
SOCIAL_AUTH_PASSWORD=#use your password

EMAIL_HOST = 'sandbox.smtp.mailtrap.io'
EMAIL_HOST_USER = #use your KEY
EMAIL_HOST_PASSWORD = #use your password
EMAIL_PORT = '587'

SOCIAL_AUTH_FACEBOOK_KEY = #use your KEY
SOCIAL_AUTH_FACEBOOK_SECRET = #use your KEY

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
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db_name',          # Replace with your PostgreSQL database name
        'USER': 'your_db_user',          # Replace with your PostgreSQL username
        'PASSWORD': 'your_db_password',  # Replace with your PostgreSQL password
        'HOST': 'localhost',             # Or the IP address of your PostgreSQL server
        'PORT': '5432',                  # Default PostgreSQL port
    }
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
