import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_notification(self, event):
        """
        Handler for the 'send_notification' event.
        """
        message = event['message']
        image_url = event.get('image_url')  # Safely get the image_url

        # ✨ EDIT: Send both message and image_url to the client
        await self.send(text_data=json.dumps({
            'message': message,
            'image_url': image_url,
        }))