from django.contrib import admin
from django.utils.html import format_html

from .models import BalanceWithdrawRequest, ReturnRequest, Transaction

@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'product', 'reason', 'status', 'amount', 'created_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('user__username', 'order__order_number', 'product__name', 'supplier__user__username')
    readonly_fields = ('id', 'image_thumbnail', 'created_at', 'updated_at', 'amount')
    autocomplete_fields = ['user', 'order', 'product', 'supplier']
    
    fieldsets = (
        ('Core Info', {
            'fields': ('user', 'order', 'product', 'supplier', 'quantity', 'status', 'reason', 'amount')
        }),
        ('User Evidence', {
            'fields': ('image', 'image_thumbnail')
        }),
    )

    def image_thumbnail(self, obj):
        if obj.image:
            return format_html('<a href="{0}"><img src="{0}" style="max-width: 150px; max-height: 150px;" /></a>', obj.image.url)
        return "No Image"
    image_thumbnail.short_description = 'Image Thumbnail'

@admin.register(BalanceWithdrawRequest)
class BalanceWithdrawRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'transfer_type', 'transfer_status', 'created_at')
    list_filter = ('transfer_type', 'transfer_status', 'created_at')
    search_fields = ('user__username', 'transfer_number')
    readonly_fields = ('id', 'created_at')
    autocomplete_fields = ['user', 'related_transaction']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'transaction_type', 'amount', 'created_at', 'related_object')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('id', 'created_at')
    autocomplete_fields = ['user']