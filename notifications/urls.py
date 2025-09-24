from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('myNotifications', views.NotificationViewSet, basename='myNotifications')

urlpatterns = [
    path('', include(router.urls)),
    path('send-to-suppliers/', views.send_notification_to_suppliers, name='send-to-suppliers'),
    
]