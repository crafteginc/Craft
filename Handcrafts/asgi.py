from notifications.routing import websocket_urlpatterns as notifications_ws_urlpatterns
from chatapp.routing import websocket_urlpatterns as chatapp_ws_urlpatterns
import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.security.websocket import AllowedHostsOriginValidator 
from . midleware import TokenAuthMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Handcrafts.settings.local")

websocket_urlpatterns = [
    *notifications_ws_urlpatterns,
    *chatapp_ws_urlpatterns,
]

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
       "websocket": AllowedHostsOriginValidator(  # new
        TokenAuthMiddleware(URLRouter(websocket_urlpatterns)))
        }
)