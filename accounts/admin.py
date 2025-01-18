from django.contrib import admin
from .models import User, Customer, Supplier, Delivery, Address, Follow, OneTimePassword

class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_verified')
    search_fields = ('email', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active', 'is_verified', 'is_customer', 'is_supplier', 'is_delivery')
    ordering = ('email',)

class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'CreditCardNO', 'CreditCardType')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    list_filter = ('CreditCardType',)

class SupplierAdmin(admin.ModelAdmin):
    list_display = ('user', 'CategoryTitle', 'Rating', 'Orders', 'FollowersNo')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'CategoryTitle')
    list_filter = ('CategoryTitle', 'Rating')
    ordering = ('-Rating',)

class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('user', 'VehicleModel', 'VehicleColor', 'plateNO', 'Rating', 'Orders', 'ExperienceYears')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'VehicleModel', 'plateNO')
    list_filter = ('Rating', 'ExperienceYears')
    ordering = ('-Rating',)

class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'BuildingNO', 'Street', 'City', 'State')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'Street', 'City', 'State')
    list_filter = ('City', 'State')

class FollowAdmin(admin.ModelAdmin):
    # Display the follower's name and the supplier's name in the admin list
    def get_follower_name(self, obj):
        return obj.follower.user.get_full_name if obj.follower else 'No follower'

    get_follower_name.admin_order_field = 'follower'  # Allows sorting by follower name
    get_follower_name.short_description = 'Follower'  # Custom column header

    list_display = ('get_follower_name', 'supplier')

    # Search functionality: allows searching by follower's ID and supplier's info
    search_fields = (
        'follower_object_id',  # Allows searching by the ID of the follower
        'supplier__user__email',
        'supplier__user__first_name',
        'supplier__user__last_name',
        'follower__user__email',  # To allow searching by the follower's email
        'follower__user__first_name',  # To allow searching by the follower's first name
        'follower__user__last_name'  # To allow searching by the follower's last name
    )

    # Filter options: allows filtering by follower type (Customer/Supplier) and supplier
    list_filter = ('follower_content_type', 'supplier')

class OneTimePasswordAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'otp')

admin.site.register(User, UserAdmin)
admin.site.register(Customer, CustomerAdmin)
admin.site.register(Supplier, SupplierAdmin)
admin.site.register(Delivery, DeliveryAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(Follow, FollowAdmin)
admin.site.register(OneTimePassword, OneTimePasswordAdmin)
