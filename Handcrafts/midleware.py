from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from channels.middleware import BaseMiddleware
from accounts.models import User

@database_sync_to_async
def get_user(token_key):
    try:
        token = AccessToken(token_key)
        user = User.objects.get(id=token['user_id'])
        return user
    except Exception:
        return AnonymousUser()

class TokenAuthMiddleware(BaseMiddleware):

    def __init__(self, inner):
        super().__init__(inner)

    async def __call__(self, scope, receive, send):
        # Default to an anonymous user
        scope['user'] = AnonymousUser()
        
        # Get the token from the headers
        headers = dict(scope.get('headers', []))
        if b'authorization' in headers:
            try:
                token_type, token_key = headers[b'authorization'].decode().split()
                if token_type.lower() == 'bearer':
                    # If a token is present, try to authenticate the user
                    scope['user'] = await get_user(token_key)
            except (ValueError, KeyError):
                # Malformed token, user remains anonymous
                pass

        # This is the crucial log message
        print(f"WebSocket connection attempt by user: {scope['user']}")

        return await super().__call__(scope, receive, send)