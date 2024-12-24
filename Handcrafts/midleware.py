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
    except Exception as e:
        print(f"Error retrieving user: {e}")
        return AnonymousUser()

class TokenAuthMiddleware(BaseMiddleware):

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        headers = dict(scope['headers'])
        if b'authorization' in headers:
            try:
                token_type, token_key = headers[b'authorization'].decode().split(' ')
                if token_type.lower() == 'bearer':
                    user = await get_user(token_key)
                    print(f"Token Key: {token_key}")
                    print(f"Authenticated User: {user}")
                    scope['user'] = user
                else:
                    print("Invalid token type")
            except ValueError as e:
                print(f"Error in token extraction: {e}")
        else:
            print("Authorization header not found")
        return await super().__call__(scope, receive, send)
