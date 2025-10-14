from django.contrib.postgres.search import SearchVector
import django_filters
from .models import Product

class ProductFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method='filter_by_search', label='Search') 
    min_price = django_filters.NumberFilter(field_name="UnitPrice", lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name="UnitPrice", lookup_expr='lte')
    rating = django_filters.NumberFilter(field_name="Rating", lookup_expr='gte') 
    
    class Meta:
        model = Product
        fields = ['Category', 'Supplier', 'search', 'min_price', 'max_price', 'rating'] 

    def filter_by_search(self, queryset, name, value):
        """
        Annotates the queryset with a search vector and filters based on it.
        """
        return queryset.annotate(
            search=SearchVector('ProductName', 'ProductDescription'),
        ).filter(search=value)