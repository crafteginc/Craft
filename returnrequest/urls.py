from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('return-requests', views.ReturnRequestViewSet, basename='return-request')
router.register('withdraw-requests', views.BalanceWithdrawRequestViewSet, basename='withdraw-request')
router.register('transactions', views.TransactionViewSet, basename='transaction')

urlpatterns = [
    path('', include(router.urls)),
]