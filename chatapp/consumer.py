import base64
import json
import secrets

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.files.base import ContentFile

from accounts.models import User
from .tasks import send_chat_notification_task
from .models import Conversation, Message
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
        conversation = Conversation.objects.select_related('initiator', 'receiver').get(id=int(self.room_name))
        message_attachment = None

        if attachment_data:
            try:
                file_str, file_ext = attachment_data["data"], attachment_data["format"]
                file_data = ContentFile(
                    base64.b64decode(file_str), name=f"{secrets.token_hex(8)}.{file_ext}"
                )
                message_attachment = file_data
            except Exception as e:
                print(f"Error handling attachment: {e}")

        message = Message.objects.create(
            sender=self.user,
            text=text,
            attachment=message_attachment,
            conversation=conversation,
        )

        recipient = (
            conversation.receiver
            if conversation.initiator == self.user
            else conversation.initiator
        )
        
        # ✨ Offload notification to Celery
        notification_message = f"You have a new message from {self.user.get_full_name}."
        send_chat_notification_task.delay(
            self.user.id, recipient.id, notification_message, conversation.id
        )
        
        return MessageSerializer(instance=message).data