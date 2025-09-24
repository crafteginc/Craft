import os
from django.core.asgi import get_asgi_application

# Set the settings module for Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Handcrafts.settings')

# Initialize the Django application BEFORE importing routing and middleware.
application = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from chatapp.routing import websocket_urlpatterns as chatapp_ws_urlpatterns
from notifications.routing import websocket_urlpatterns as notifications_ws_urlpatterns
from .midleware import TokenAuthMiddleware

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": TokenAuthMiddleware(
            URLRouter(
                chatapp_ws_urlpatterns + notifications_ws_urlpatterns
            )
        ),
    }
)