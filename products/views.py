from django.shortcuts import render, get_object_or_404
from .serializers import *
from accounts.serializers import AcountProductSerializer 
from .models import Category, Product, ProImage, MatCategory
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
from PIL import Image


class Categories(APIView):
    #permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        categories = Category.objects.all()
        serializer = CategorySerializer(categories,many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)

class ProductsByCategory(APIView):
    #permission_classes = [permissions.IsAuthenticated]
    def get(self, request, Slug):
        try:
            category = Category.objects.get(Slug=Slug)
            products = category.CatPro.filter(OutOfStock = False)
            serializer = ProductSerializer(products, many=True)
            return Response(serializer.data)
        except Category.DoesNotExist:
            return Response({"message": "Category not found"}, status=404)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

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

        # Automatically create or get the collection based on category
        category_name = product.Category.Title
        collection, created = Collection.objects.get_or_create(
            supplier=supplier_instance,
            name=category_name
        )
        
        # Create a collection item for the new product
        CollectionItem.objects.create(collection=collection, product=product)

    def perform_update(self, serializer):
        instance = serializer.instance
        if not self.request.user.is_supplier or instance.Supplier.user != self.request.user:
            raise ValidationError("You are not allowed to update this product.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_supplier or instance.Supplier.user != self.request.user:
            raise ValidationError("You are not allowed to delete this product.")
        instance.delete()

class FollowedSuppliersProducts(APIView):
    def get(self, request):
        # Check if the user is authenticated and is a customer
        if not request.user.is_authenticated or not request.user.is_customer:
            return Response({"error": "Not authorized"}, status=status.HTTP_401_UNAUTHORIZED)
        # Get the customer
        customer = request.user.customer
        # Get the suppliers that the customer has followed
        followed_suppliers = Follow.objects.filter(Customer=customer).values_list('Supplier', flat=True)
        # Get the products of the followed suppliers
        products = Product.objects.filter(Supplier__in=followed_suppliers)
        # Order the products by their Publish_Date (newest first)
        products = products.order_by('-Publish_Date')
        newest_products = products[:10]    
        # Serialize the products and return the response
        serializer = AcountProductSerializer(newest_products, many=True)
        return Response(serializer.data)
    
class Mataterials(APIView):
    #permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        materials = MatCategory.objects.all()
        serializer = MatCategorySerializer(materials,many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)

class ProductsByMaterials(APIView):
    #permission_classes = [permissions.IsAuthenticated]
    def get(self, request, Slug):
        try:
            material = MatCategory.objects.get(Slug=Slug)
            products = material.MatCatPro.filter(OutOfStock =  False)
            serializer = AcountProductSerializer(products, many=True)
            return Response(serializer.data)
        except MatCategory.DoesNotExist:
            return Response({"message": "material not found"}, status=404)

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
