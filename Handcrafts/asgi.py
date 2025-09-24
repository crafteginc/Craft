import os
from django.core.asgi import get_asgi_application

from channels.routing import ProtocolTypeRouter, URLRouter

from notifications.routing import websocket_urlpatterns as notifications_ws_urlpatterns
from chatapp.routing import websocket_urlpatterns as chatapp_ws_urlpatterns
from .midleware import TokenAuthMiddleware

# This line correctly sets the settings module for production
settings_module = 'Handcrafts.deployment' if 'WEBSITE_HOSTNAME' in os.environ else 'Handcrafts.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

# This is the simplified and corrected application setup
application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": TokenAuthMiddleware(
            URLRouter(
                [
                    *notifications_ws_urlpatterns,
                    *chatapp_ws_urlpatterns,
                ]
            )
        ),
    }
)