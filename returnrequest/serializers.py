from rest_framework import serializers
from orders.models import Order, OrderItem
from products.models import Product
from .models import BalanceWithdrawRequest, ReturnRequest, Transaction

class ReturnRequestCreateSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), write_only=True
    )
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), write_only=True
    )
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=ReturnRequest.ReturnReason.choices)
    image = serializers.ImageField(required=False, allow_null=True, use_url=True)

    def validate(self, data):
        user = self.context['request'].user
        product = data.get('product')
        order = data.get('order')
        quantity = data.get('quantity')

        if order.user != user:
            raise serializers.ValidationError("You can only create returns for your own orders.")

        try:
            order_item = OrderItem.objects.get(order=order, product=product)
        except OrderItem.DoesNotExist:
            raise serializers.ValidationError("This product was not found in the specified order.")

        if quantity > order_item.quantity:
            raise serializers.ValidationError(f"Quantity cannot exceed the ordered quantity ({order_item.quantity}).")

        if ReturnRequest.objects.filter(user=user, product=product, order=order).exists():
            raise serializers.ValidationError("A return request for this product in this order already exists.")
            
        return data

class ReturnRequestListSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    
    class Meta:
        model = ReturnRequest
        fields = ("id", "order_number", "created_at" , "product_name", "amount", "image")

class ReturnRequestDetailSerializer(serializers.ModelSerializer):
    product = serializers.StringRelatedField(read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    supplier = serializers.StringRelatedField(read_only=True)
    status = serializers.CharField(source='get_status_display', read_only=True)
    reason = serializers.CharField(source='get_reason_display', read_only=True)
    image = serializers.ImageField(read_only=True, use_url=True)
    
    class Meta:
        model = ReturnRequest
        fields = "__all__"

class BalanceWithdrawRequestSerializer(serializers.ModelSerializer):
    user = serializers.StringRelatedField(read_only=True)
    transfer_status = serializers.CharField(source='get_transfer_status_display', read_only=True)

    class Meta:
        model = BalanceWithdrawRequest
        fields = ['id', 'user', 'amount', 'transfer_number', 'transfer_type', 'notes', 'transfer_status', 'created_at']
        read_only_fields = ['id', 'user', 'transfer_status', 'created_at']

class TransactionSerializer(serializers.ModelSerializer):
    transaction_type = serializers.CharField(source='get_transaction_type_display', read_only=True)
    
    class Meta:
        model = Transaction
        fields = ['id', 'transaction_type', 'amount', 'created_at']