from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied
from .models import Review
from .serializers import ReviewSerializer
from accounts.permissions import IsAuthenticated
from products.models import Product
from course.models import Course
from accounts.models import Delivery, Supplier

# Assuming StandardResultsSetPagination is defined elsewhere
from products.views import StandardResultsSetPagination

class ReviewCreateView(generics.CreateAPIView):
    """
    API view for creating a new review.
    Handles creation for products, courses, deliveries, and suppliers.
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

class ReviewUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view for retrieving, updating, and deleting a specific review.
    A user can only update or delete their own review.
    """
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            instance = super().get_object()
        except Review.DoesNotExist:
            raise NotFound({"detail": "Review not found."})
        
        # Check if the current user owns the review
        if instance.customer.user != self.request.user:
            raise PermissionDenied("You do not have permission to perform this action.")
        
        return instance

class ReviewListView(generics.ListAPIView):
    """
    API view to list reviews for a specific object (product, course, etc.).
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        product_id = self.kwargs.get('product_id')
        course_id = self.kwargs.get('course_id')
        delivery_id = self.kwargs.get('delivery_id')
        supplier_id = self.kwargs.get('supplier_id')

        if product_id:
            if not Product.objects.filter(id=product_id).exists():
                raise NotFound({"detail": "Product not found."})
            queryset = Review.objects.filter(product_id=product_id)
            if not queryset.exists():
                raise NotFound({"detail": "No reviews found for this product."})
            return queryset
        
        elif course_id:
            if not Course.objects.filter(id=course_id).exists():
                raise NotFound({"detail": "Course not found."})
            queryset = Review.objects.filter(course_id=course_id)
            if not queryset.exists():
                raise NotFound({"detail": "No reviews found for this course."})
            return queryset

        elif delivery_id:
            if not Delivery.objects.filter(id=delivery_id).exists():
                raise NotFound({"detail": "Delivery not found."})
            queryset = Review.objects.filter(delivery_id=delivery_id)
            if not queryset.exists():
                raise NotFound({"detail": "No reviews found for this delivery."})
            return queryset
            
        elif supplier_id:
            if not Supplier.objects.filter(id=supplier_id).exists():
                raise NotFound({"detail": "Supplier not found."})
            

            products = Product.objects.filter(Supplier_id=supplier_id)
            if not products.exists():
                raise NotFound({"detail": "No products found for this supplier."})
            
            queryset = Review.objects.filter(product__in=products)
            
            
            supplier_reviews = Review.objects.filter(supplier_id=supplier_id)
            queryset = queryset | supplier_reviews 
            
            if not queryset.exists():
                raise NotFound({"detail": "No reviews found for this supplier."})
            
            return queryset.distinct() 

        raise NotFound({"detail": "Invalid review list endpoint."})