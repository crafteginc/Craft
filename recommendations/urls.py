from django.urls import path
from .views import ProductRecommendationAPIView

urlpatterns = [
    path('products/<int:product_id>/', ProductRecommendationAPIView.as_view(), name='product-recommendations'),
]