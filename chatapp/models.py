from django.db import models
from django.db.models import Q
from accounts.models import User

class ConversationManager(models.Manager):
    def get_or_create_personal_convo(self, user1, user2):
        """
        Gets or creates a personal conversation between two users.
        """
        convo = self.filter(
            Q(initiator=user1, receiver=user2) |
            Q(initiator=user2, receiver=user1)
        ).first()

        if convo is None:
            convo = self.create(initiator=user1, receiver=user2)
        
        return convo

class Conversation(models.Model):
    initiator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="convo_starter"
    )
    receiver = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="convo_participant"
    )
    start_time = models.DateTimeField(auto_now_add=True)

    objects = ConversationManager()

    def __str__(self):
        return f"Conversation between {self.initiator} and {self.receiver}"


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.SET_NULL,
                               null=True, related_name='message_sender')
    text = models.CharField(max_length=200, blank=True)
    attachment = models.FileField(blank=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-timestamp',)

    def __str__(self):
        return f"Message from {self.sender} at {self.timestamp}"