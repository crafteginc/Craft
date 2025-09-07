from django.urls import path
from .views import ReviewCreateView, ReviewUpdateDeleteView, ReviewListView

urlpatterns = [
    # Single endpoint for creating a review.
    # The serializer handles the type of review based on the request body (e.g., 'product_id').
    path('reviews/', ReviewCreateView.as_view(), name='review-create'),

    # Single endpoint for retrieving, updating, and deleting a specific review by its primary key.
    path('reviews/<int:pk>/', ReviewUpdateDeleteView.as_view(), name='review-update-delete'),
    
    # Endpoints to list reviews for a specific object type.
    # Each URL pattern maps to the same ReviewListView, which uses the URL kwargs to filter.
    path('products/<int:product_id>/reviews/', ReviewListView.as_view(), name='product-review-list'),
    path('courses/<int:course_id>/reviews/', ReviewListView.as_view(), name='course-review-list'),
    path('deliveries/<int:delivery_id>/reviews/', ReviewListView.as_view(), name='delivery-review-list'),
    path('suppliers/<int:supplier_id>/reviews/', ReviewListView.as_view(), name='supplier-review-list'),
]