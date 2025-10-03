import json
import base64
import secrets
from django.core.files.base import ContentFile
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message, Conversation
from .serializers import MessageSerializer
from notifications.services import create_notification_for_user
from accounts.models import User


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
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": data.get("message", ""),
                "attachment": data.get("attachment"),
            },
        )

    async def chat_message(self, event):
        message_data = await self.create_message(
            text=event["message"],
            attachment_data=event.get("attachment")
        )

        await self.send(text_data=json.dumps(message_data))

    @database_sync_to_async
    def create_message(self, text, attachment_data=None):
        """
        Creates a new message and sends a notification to the recipient.
        """
        conversation = Conversation.objects.select_related('initiator', 'receiver').get(id=int(self.room_name))
        message_attachment = None

        if attachment_data:
            try:
                file_str, file_ext = attachment_data["data"], attachment_data["format"]
                file_data = ContentFile(
                    base64.b64decode(file_str), name=f"{secrets.token_hex(8)}.{file_ext}"
                )
                message_attachment = file_data
            except (KeyError, TypeError, base64.BinasciiError) as e:
                print(f"Error handling attachment: {e}")
                pass

        message = Message.objects.create(
            sender=self.user,
            text=text,
            attachment=message_attachment,
            conversation=conversation,
        )

        # ✨ NOTIFICATION: Inform the other participant of the new message
        recipient = (
            conversation.receiver
            if conversation.initiator == self.user
            else conversation.initiator
        )
        
        create_notification_for_user(
            user=recipient,
            message=f"You have a new message from {self.user.get_full_name}.",
            related_object=conversation,
            image=message.attachment # Pass the attachment as the notification image
        )
        
        return MessageSerializer(instance=message).data