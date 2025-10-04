from django.contrib import admin
from .models import FrequentlyBoughtTogether, UserProductView

@admin.register(FrequentlyBoughtTogether)
class FrequentlyBoughtTogetherAdmin(admin.ModelAdmin):
    list_display = ('product', 'recommended_product', 'score')
    search_fields = ('product__ProductName', 'recommended_product__ProductName')

@admin.register(UserProductView)
class UserProductViewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'viewed_at')
    search_fields = ('user__username', 'product__ProductName')