from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from products.models import Product
from products.serializers import ProductSerializer  
from .models import FrequentlyBoughtTogether, UserProductView
from .services import get_collaborative_filtering_recommendations

class ProductRecommendationAPIView(APIView):
    def get(self, request, product_id):
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)

        # Track the product view for the current user (if authenticated)
        if request.user.is_authenticated:
            UserProductView.objects.get_or_create(user=request.user, product=product)

        # Get "Frequently Bought Together" recommendations
        fbt_products = FrequentlyBoughtTogether.objects.filter(product=product).order_by('-score')[:5]
        fbt_serializer = ProductSerializer([rec.recommended_product for rec in fbt_products], many=True)

        # Get "Customers Who Viewed This Also Viewed" (Collaborative Filtering) recommendations
        collab_products = get_collaborative_filtering_recommendations(product)
        collab_serializer = ProductSerializer(collab_products, many=True)

        return Response({
            "frequently_bought_together": fbt_serializer.data,
            "customers_also_viewed": collab_serializer.data,
        }, status=status.HTTP_200_OK)