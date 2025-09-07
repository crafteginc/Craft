from django.contrib import admin
from .models import Wishlist, WishlistItem, Cart, CartItems, Order, OrderItem, Coupon, Warehouse, Shipment, ShipmentItem,CouponUsage

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'Created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    ordering = ('-Created_at',)

@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('wishlist', 'product')
    search_fields = ('wishlist__user__email', 'wishlist__user__first_name', 'wishlist__user__last_name', 'product__ProductName')
    list_filter = ('wishlist__Created_at',)

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('User', 'Created_at')
    search_fields = ('User__email', 'User__first_name', 'User__last_name')
    ordering = ('-Created_at',)

@admin.register(CartItems)
class CartItemsAdmin(admin.ModelAdmin):
    list_display = ('CartID', 'Product', 'Quantity')
    search_fields = ('CartID__User__email', 'CartID__User__first_name', 'CartID__User__last_name', 'Product__ProductName')
    list_filter = ('CartID__Created_at',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'created_at', 'total_amount', 'paid')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    list_filter = ('created_at', 'paid')
    ordering = ('-created_at',)

class ShipmentItemInline(admin.TabularInline):
    model = ShipmentItem
    extra = 0
    fields = ('order_item', 'quantity',)
    readonly_fields = ('order_item', 'quantity',)

@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'supplier', 'status', 'from_state', 'to_state', 'delivery_person')
    list_filter = ('status', 'from_state', 'to_state', 'delivery_person')
    search_fields = ('order__id', 'supplier__user__email', 'supplier__user__first_name')
    inlines = [ShipmentItemInline]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price', 'created_at')
    search_fields = ('order__user__email', 'order__user__first_name', 'order__user__last_name', 'product__ProductName')
    list_filter = ('created_at',)
    ordering = ('-created_at',)

@admin.register(ShipmentItem)
class ShipmentItemAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'order_item', 'quantity')
    search_fields = ('shipment__id', 'order_item__product__ProductName')
    list_filter = ('shipment__status',)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'supplier', 'discount', 'discount_type', 'valid_from', 'valid_to', 'active', 'max_uses', 'uses_count')
    list_filter = ('active', 'valid_from', 'valid_to', 'discount_type', 'supplier')
    search_fields = ('code', 'supplier__user__email', 'products__ProductName')
    readonly_fields = ('uses_count',)
    filter_horizontal = ('products',)
    fieldsets = (
        (None, {
            'fields': ('code', 'supplier', 'discount', 'discount_type', 'min_purchase_amount', 'terms')
        }),
        ('Availability', {
            'fields': ('valid_from', 'valid_to', 'active')
        }),
        ('Usage Limits', {
            'fields': ('max_uses', 'uses_count', 'max_uses_per_user')
        }),
        ('Applicable Products', {
            'fields': ('products',)
        }),
    )
@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ('user', 'coupon', 'used_at')
    list_filter = ('coupon', 'used_at')
    search_fields = ('user__email', 'coupon__code')
    readonly_fields = ('used_at',)

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'Address', 'contact_person', 'contact_phone', 'delivery_fee')
    search_fields = ('name', 'contact_person', 'contact_phone')
    ordering = ('name',)