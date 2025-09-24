import os
from django.core.asgi import get_asgi_application
from django.conf import settings # Import Django settings

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from notifications.routing import websocket_urlpatterns as notifications_ws_urlpatterns
from chatapp.routing import websocket_urlpatterns as chatapp_ws_urlpatterns
from .midleware import TokenAuthMiddleware

# This should point to your production settings file in production
settings_module = 'Handcrafts.deployment' if 'WEBSITE_HOSTNAME' in os.environ else 'Handcrafts.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

application = get_asgi_application()

websocket_urlpatterns = [
    *notifications_ws_urlpatterns,
    *chatapp_ws_urlpatterns,
]

# Define the base websocket stack
websocket_application = TokenAuthMiddleware(URLRouter(websocket_urlpatterns))

# In production, wrap the stack with the origin validator for security
if not settings.DEBUG:
    websocket_application = AllowedHostsOriginValidator(websocket_application)


application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": websocket_application,
    }
)