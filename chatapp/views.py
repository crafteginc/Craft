from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch, Q
from accounts.models import User
from .models import Conversation, Message
from .serializers import ConversationListSerializer, ConversationSerializer

@api_view(['POST'])
def start_convo(request, user_id):
    participant = get_object_or_404(User, id=user_id)
    
    if request.user == participant:
        return Response(
            {'message': 'You cannot start a conversation with yourself.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    conversation = Conversation.objects.get_or_create_personal_convo(request.user, participant)
    serializer = ConversationSerializer(instance=conversation, context={'request': request})
    return Response(serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
def get_conversation(request, convo_id):
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related(
            Prefetch('messages', queryset=Message.objects.order_by('timestamp'))
        ), 
        id=convo_id
    )
    
    # Ensure the requesting user is part of the conversation
    if request.user not in [conversation.initiator, conversation.receiver]:
        return Response(status=status.HTTP_403_FORBIDDEN)
        
    serializer = ConversationSerializer(instance=conversation, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
def conversations(request):
    conversation_list = Conversation.objects.filter(
        Q(initiator=request.user) | Q(receiver=request.user)
    ).prefetch_related(
        Prefetch('messages', queryset=Message.objects.order_by('-timestamp')[:1])
    ).select_related('initiator', 'receiver')

    serializer = ConversationListSerializer(instance=conversation_list, many=True, context={'request': request})
    return Response(serializer.data)