from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register('my-notifications', views.NotificationViewSet, basename='my-notifications')

urlpatterns = [
    path('', include(router.urls)),
    path('send-to-suppliers/', views.send_to_suppliers_view, name='send-to-suppliers'),
    path('send-to-all/', views.send_to_all_users_view, name='send-to-all'),
]