from .models import Order, OrderItem, Cart, CartItems, Wishlist, WishlistItem, Warehouse, Shipment, ShipmentItem
from accounts.serializers import AddressSerializer
from products.models import Product
from .models import Coupon
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from accounts.models import User
from products.serializers import ProductImageSerializer
from collections import defaultdict
from decimal import Decimal

class SimpleProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    class Meta:
        model = Product
        fields = ["id",'images',"ProductName", "UnitPrice"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data['images']:
            data['images'] = [data['images'][0]]
        return data
class OrderItemProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    class Meta:
        model = Product
        fields = ["id",'images',"ProductName"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data['images']:
            data['images'] = [data['images'][0]]
        return data

class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ["id", "name", "PhoneNO"]

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

class WishlistItemSerializer(serializers.ModelSerializer):
    product = SimpleProductSerializer(many=False, allow_null=True)

    class Meta:
        model = WishlistItem
        fields = ["id", "product"]

class WishlistSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    items = WishlistItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Wishlist
        fields = ["id", "items"]

class AddWishlistItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(write_only=True)

    def validate_product_id(self, value):
        product = Product.objects.filter(id=value).first()
        if not product:
            raise serializers.ValidationError("There is no product associated with the given ID")
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        product_id = self.validated_data["product_id"]
        wishlist, _ = Wishlist.objects.get_or_create(user=user)

        product = Product.objects.get(id=product_id)
        if product.supplier.user == user:
            raise serializers.ValidationError("You cannot add your own product to the wishlist")

        wishlist_item, _ = WishlistItem.objects.get_or_create(wishlist=wishlist, product=product)
        self.instance = wishlist_item

        return self.instance

    class Meta:
        model = WishlistItem
        fields = ["id", "product_id"]

class CartItemSerializer(serializers.ModelSerializer):
    product = SimpleProductSerializer(source="Product", many=False, read_only=True)
    sub_total = serializers.SerializerMethodField(method_name="total")

    class Meta:
        model = CartItems
        fields = ["id", "Quantity", "product", "sub_total"]

    def total(self, cart_item):
        if cart_item.Product:
            return cart_item.Quantity * cart_item.Product.UnitPrice
        return 0

class CartSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(read_only=True)
    items = CartItemSerializer(many=True, read_only=True)
    grand_total = serializers.SerializerMethodField(method_name='main_total')
    
    class Meta:
        model = Cart
        fields = ["id", "items", "grand_total"]
        
    def main_total(self, cart):
        items = cart.items.all()
        total = sum([item.Quantity * item.Product.UnitPrice for item in items if item.Product])
        return total
       
class AddCartItemSerializer(serializers.ModelSerializer):
    Product_id = serializers.IntegerField(write_only=True)
    Color = serializers.CharField(required=False, allow_blank=True)
    Size = serializers.CharField(required=False, allow_blank=True)

    def validate_product_id(self, value):
        product = Product.objects.filter(id=value).first()
        if not product:
            raise serializers.ValidationError({"detail":"There is no product associated with the given ID"})
        return value

    def save(self, **kwargs):
        user = self.context['request'].user
        Product_id = self.validated_data["Product_id"]
        quantity = self.validated_data["Quantity"]
        color = self.validated_data.get("Color", "")
        size = self.validated_data.get("Size", "")
        
        cart, _ = Cart.objects.get_or_create(User=user)
        product = Product.objects.get(id=Product_id)

        if product.Supplier.user == user:
            raise serializers.ValidationError({"detail":"You cannot add your own product to the cart"})
        
        if quantity <= 0 or quantity > 10:
            raise serializers.ValidationError({"detail":"Quantity Must be above 0 and less than or equal to 10"})
        if quantity > product.Stock :
            raise serializers.ValidationError({"detail": f"Quantity of {product.ProductName} exceeds available stock."})
        
        try:
            cart_item = CartItems.objects.get(Product_id=Product_id, CartID=cart, Color=color, Size=size)
            if cart_item.Quantity + quantity > product.Stock:
                raise serializers.ValidationError({"detail": f"Adding this quantity of {product.ProductName} exceeds available stock."})
            cart_item.Quantity += quantity
            cart_item.save()
            self.instance = cart_item
        except CartItems.DoesNotExist:
            self.instance = CartItems.objects.create(
                CartID=cart,
                Product_id=Product_id,
                Quantity=quantity,
                Color=color,
                Size=size
            )

        return self.instance

    class Meta:
        model = CartItems
        fields = ["id", "Product_id", "Quantity", "Color", "Size"]

class UpdateCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItems
        fields = ["Quantity"]

class OrderCreateSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    class Meta:
        model = Order
        exclude = ("paid", "status")
        
class OrderItemListRetrieveSerializer(serializers.ModelSerializer):
    product = OrderItemProductSerializer()
    cost = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ("id", "product", "quantity", "price", "cost")

    def get_cost(self, obj: OrderItem):
        return obj.get_cost()

class ShipmentItemSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()

    class Meta:
        model = ShipmentItem
        fields = ["quantity", "product"]

    def get_product(self, obj):
        return SimpleProductSerializer(obj.order_item.product).data

class ShipmentSerializer(serializers.ModelSerializer):
    items = ShipmentItemSerializer(many=True, read_only=True)
    confirmation_code = serializers.SerializerMethodField()
    status = serializers.CharField(source='get_status_display')

    class Meta:
        model = Shipment
        fields = ["confirmation_code", "status", "items"]

    def get_confirmation_code(self, obj: Shipment):
        request = self.context.get('request')
        if request and request.user == obj.order.user:
            return obj.confirmation_code
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('confirmation_code') is None:
            data.pop('confirmation_code')
        return data

class OrderListRetrieveSerializer(serializers.ModelSerializer):
    confirmation_code = serializers.SerializerMethodField()
    order_items = OrderItemListRetrieveSerializer(many=True, source='items')

    class Meta:
        model = Order
        fields = ("id", "final_amount", "paid", "created_at", "confirmation_code", "order_items")

    def get_confirmation_code(self, obj: Order):
        latest_shipment = obj.shipments.order_by('-id').first()
        if latest_shipment and self.context.get('request').user == obj.user:
            return latest_shipment.confirmation_code
        return None

class SupplierOrderListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "created_at", "paid", "status", "final_amount")

class SupplierOrderRetrieveSerializer(serializers.ModelSerializer):
    order_items = OrderItemListRetrieveSerializer(many=True, source='items')
    address = AddressSerializer()
    payment_method = serializers.CharField(source='get_payment_method_display')
    status = serializers.CharField(source='get_status_display')

    class Meta:
        model = Order
        fields = (
            "id", "user", "order_items", "address", "payment_method",
            "total_amount", "discount_amount", "delivery_fee", "final_amount", "status"
        )        

class ReturnRequestListRetrieveSerializer(serializers.ModelSerializer):
    items = OrderItemListRetrieveSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["items",]
        ref_name = 'Orders_ReturnRequestListRetrieveSerializer'

class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'discount', 'discount_type', 'valid_from', 'valid_to',
            'active', 'min_purchase_amount', 'max_uses', 'max_uses_per_user',
            'products'
        ]
        read_only_fields = ['supplier', 'uses_count']

    def validate(self, data):
        if data['valid_from'] >= data['valid_to']:
            raise serializers.ValidationError("Valid from date must be before valid to date.")
        
        # Validation for discount type
        if data.get('discount_type') == 'percentage' and data.get('discount') > 100:
            raise serializers.ValidationError("Percentage discount cannot be more than 100.")
            
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        if not user.is_authenticated or not hasattr(user, 'supplier'):
            raise serializers.ValidationError("User is not a supplier.")
        
        validated_data['supplier'] = user.supplier
        products_data = validated_data.pop('products', [])
        coupon = super().create(validated_data)
        coupon.products.set(products_data)
        return coupon

class OrderDeliverSerializer(serializers.ModelSerializer):
    confirmation_code = serializers.CharField(write_only=True)
    class Meta:
        model = Order
        fields = ['confirmation_code']

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ['id','name',]