from rest_framework import serializers
from accounts.models import User
from .models import Conversation, Message

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name']

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'sender', 'text', 'attachment', 'timestamp']

class ConversationListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing conversations. Shows the other participant and the last message.
    """
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'other_user', 'last_message']

    def get_other_user(self, instance):
        if instance.initiator == self.context['request'].user:
            return UserSerializer(instance.receiver).data
        return UserSerializer(instance.initiator).data
        
    def get_last_message(self, instance):
        # Access the prefetched message
        last_message = instance.messages.first()
        if last_message:
            return MessageSerializer(instance=last_message).data
        return None

class ConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for a single, detailed conversation view.
    """
    initiator = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'initiator', 'receiver', 'start_time', 'messages']