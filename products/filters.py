import django_filters
from .models import Product

class ProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains') # Changed to 'icontains' for partial matching
    keyword = django_filters.CharFilter(field_name="ProductName", lookup_expr="icontains")
    min_price = django_filters.NumberFilter(field_name="UnitPrice", lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name="UnitPrice", lookup_expr='lte')
    rating = django_filters.NumberFilter(field_name="Rating", lookup_expr='gte') # Filter by minimum rating
    
    class Meta:
        model = Product
        fields = ['Category', 'Supplier', 'keyword', 'min_price', 'max_price', 'rating']