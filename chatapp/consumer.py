import json
import base64
import secrets
from django.core.files.base import ContentFile
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message, Conversation
from .serializers import MessageSerializer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        data = json.loads(text_data)
        
        # Pass the message and attachment data to the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": data.get("message", ""),
                "attachment": data.get("attachment"), # The attachment dict from the client
            },
        )

    async def chat_message(self, event):
        # Create the message in the database and get the serialized data
        message_data = await self.create_message(
            text=event["message"],
            attachment_data=event.get("attachment")
        )

        # Send the complete message object back to the client
        await self.send(text_data=json.dumps(message_data))

    @database_sync_to_async
    def create_message(self, text, attachment_data=None):
        """
        Creates a new message in the database, handling an optional file attachment.
        This method runs in a synchronous context to safely interact with the Django ORM.
        """
        conversation = Conversation.objects.get(id=int(self.room_name))
        message_attachment = None

        # --- Attachment Handling Logic ---
        if attachment_data:
            try:
                # Expects a dictionary like: {'data': 'base64_string', 'format': 'ext'}
                file_str, file_ext = attachment_data["data"], attachment_data["format"]
                
                # Decode the base64 string and create a Django ContentFile
                file_data = ContentFile(
                    base64.b64decode(file_str), name=f"{secrets.token_hex(8)}.{file_ext}"
                )
                message_attachment = file_data
            except (KeyError, TypeError, base64.BinasciiError) as e:
                # Log the error if attachment data is malformed
                print(f"Error handling attachment: {e}")
                # Continue to create the message without the attachment
                pass
        # --- End Attachment Handling ---

        message = Message.objects.create(
            sender=self.user,
            text=text,
            attachment=message_attachment, # Will be None if there's no attachment or an error occurred
            conversation=conversation,
        )
        return MessageSerializer(instance=message).data