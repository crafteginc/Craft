from django.urls import path
from .views import EarningReportView

urlpatterns = [
    path('earnings/', EarningReportView.as_view(), name='earning-report'),
]