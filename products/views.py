from .serializers import *
from accounts.serializers import AccountProductSerializer 
from .models import Category, Product, MatCategory
from accounts.models import Follow
from rest_framework.response import Response
from rest_framework import status ,permissions,viewsets
from rest_framework.viewsets import ModelViewSet
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from .filters import ProductFilter
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework .exceptions import ValidationError
from accounts.models import Supplier
from .permissions import *
from django.contrib.contenttypes.models import ContentType
from rest_framework.generics import ListAPIView

class Categories(APIView):
    #permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories,many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class ProductsByCategory(ListAPIView):
    serializer_class = ProductSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['ProductName', 'Description']  

    def get_queryset(self):
        slug = self.kwargs.get("Slug")
        try:
            category = Category.objects.get(Slug=slug)
            return category.CatPro.filter(OutOfStock=False)
        except Category.DoesNotExist:
            return []

class ProductsViewSet(ModelViewSet):
    queryset = Product.objects.filter( Stock__gt = 0 )
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['ProductName','ProductDescription']
    ordering_fields = ['UnitPrice']
    pagination_class = StandardResultsSetPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.request.method == 'POST':
            permission_classes = [permissions.IsAuthenticated, SupplierContractProvided]
        else:
            permission_classes = [permissions.AllowAny]  # Or any other permissions you want to apply for GET requests
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductSerializer
        return self.serializer_class
    
    def perform_create(self, serializer):
        if not self.request.user.is_supplier:
            raise ValidationError("Only Suppliers can create products.")
        supplier_instance = Supplier.objects.get(user=self.request.user)
        product = serializer.save(Supplier=supplier_instance)

    def perform_update(self, serializer):
        instance = serializer.instance
        if not self.request.user.is_supplier or instance.Supplier.user != self.request.user:
            raise ValidationError("You are not allowed to update this product.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_supplier or instance.Supplier.user != self.request.user:
            raise ValidationError("You are not allowed to delete this product.")
        instance.delete()

class SupplierProductsViewSet(viewsets.ModelViewSet):
    serializer_class = AccountProductSerializer
    permission_classes = [permissions.IsAuthenticated]  

    def get_queryset(self):
        supplier = self.request.user.supplier 
        return Product.objects.filter(Supplier=supplier) 
    
class FollowedSuppliersProducts(APIView):
    def get(self, request):
        # Check if the user is authenticated
        if not request.user.is_authenticated:
            return Response({"error": "Not authorized"}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if the user is a customer or supplier
        if hasattr(request.user, 'customer'):
            # User is a customer, get the customer's followed suppliers
            customer = request.user.customer
            follower_content_type = ContentType.objects.get_for_model(customer)  # ContentType for customer
            followed_suppliers = Follow.objects.filter(
                follower_content_type=follower_content_type, 
                follower_object_id=customer.id
            ).values_list('supplier', flat=True)
        
        elif hasattr(request.user, 'supplier'):
            # User is a supplier, get the supplier's followed suppliers
            supplier = request.user.supplier
            follower_content_type = ContentType.objects.get_for_model(supplier)  # ContentType for supplier
            followed_suppliers = Follow.objects.filter(
                follower_content_type=follower_content_type, 
                follower_object_id=supplier.id
            ).values_list('supplier', flat=True)
        
        else:
            return Response({"error": "User must be a customer or supplier"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the products of the followed suppliers
        products = Product.objects.filter(Supplier__in=followed_suppliers)

        # Order the products by their Publish_Date (newest first)
        products = products.order_by('-Publish_Date')

        # Get the 10 newest products
        newest_products = products[:10]    

        # Serialize the products and return the response
        serializer = TrendingProductSerializer(newest_products, many=True)
        return Response(serializer.data)
    
class Mataterials(APIView):
    #permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        materials = MatCategory.objects.all()
        serializer = MatCategorySerializer(materials,many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)

class ProductsByMaterials(ListAPIView):
    serializer_class = AccountProductSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['ProductName', 'ProductDescription']
    ordering_fields = ['UnitPrice']

    def get_queryset(self):
        slug = self.kwargs.get("Slug")
        user = self.request.user

        try:
            material = MatCategory.objects.get(Slug=slug)
            queryset = material.MatCatPro.filter(OutOfStock=False)
            
            if hasattr(user, 'supplier'):
                queryset = queryset.exclude(Supplier=user.supplier)

            return queryset
        except MatCategory.DoesNotExist:
            return Product.objects.none()

class CollectionViewSet(viewsets.ModelViewSet):
    queryset = Collection.objects.all()

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CollectionCreateUpdateSerializer
        return CollectionSerializer

    def perform_create(self, serializer):
        serializer.save(supplier=self.request.user.supplier)

    def get_queryset(self):
        return self.queryset.filter(supplier=self.request.user.supplier)

    permission_classes = [IsSupplier]

    def destroy(self, request, *args, **kwargs):
        """
        Custom destroy method to delete the collection only if the supplier
        who created it is making the request.
        """
        collection = self.get_object()  # Get the collection instance based on URL parameter
        supplier = self.request.user.supplier

        # Ensure the supplier who owns the collection is the one making the request
        if collection.supplier != supplier:
            return Response({"error": "You are not authorized to delete this collection."}, status=status.HTTP_403_FORBIDDEN)

        # Proceed to delete the collection
        collection.delete()

        return Response({"message": "Collection deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

class CollectionDetailView(APIView):
    def get(self, request, collection_id):
        try:
            # Retrieve the collection
            collection = Collection.objects.prefetch_related('items__product').get(id=collection_id)
            
            # Serialize the collection data
            serializer = CollectionSerializer(collection)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Collection.DoesNotExist:
            return Response({"error": "Collection not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LatestFollowedSuppliersCollections(APIView):
    def get(self, request):
        # Check if the user is authenticated
        if not request.user.is_authenticated:
            return Response({"error": "Not authorized"}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Determine if the user is a customer or supplier
        if hasattr(request.user, 'customer'):
            # If user is a customer, get the customer instance
            follower = request.user.customer
        elif hasattr(request.user, 'supplier'):
            # If user is a supplier, get the supplier instance
            follower = request.user.supplier
        else:
            return Response({"error": "User must be a customer or supplier"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get ContentType for the follower
        follower_content_type = ContentType.objects.get_for_model(follower)

        # Fetch the suppliers followed by the user
        followed_supplier_ids = Follow.objects.filter(
            follower_content_type=follower_content_type,
            follower_object_id=follower.id
        ).values_list('supplier_id', flat=True)

        # Fetch the latest collections from the followed suppliers
        collections = Collection.objects.filter(
            supplier__id__in=followed_supplier_ids
        ).order_by('-created_at')[:10]  # Fetch the latest 10 collections

        # Serialize the collections
        serializer = LatestCollectionSerializer(collections, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)