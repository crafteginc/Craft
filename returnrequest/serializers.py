from rest_framework import serializers
from products.models import Product
from .models import ReturnRequest, Balance_Withdraw_Request, transactions
from orders.serializers import UserSerializer, AddressSerializer, SimpleProductSerializer
from orders.models import OrderItem

class ReturnRequestCreateSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(write_only=True)
    quantity = serializers.IntegerField()
    order_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = ReturnRequest
        fields = ['product_id', 'quantity', 'order_id']

    def validate(self, data):
        product_id = data.get('product_id')
        quantity = data.get('quantity')
        order_id = data.get('order_id')
        user = self.context['request'].user

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product does not exist.")
        
        try:
            order = OrderItem.objects.get(order_id=order_id, product=product)
        except OrderItem.DoesNotExist:
            raise serializers.ValidationError("Product not found in this order.")

        if quantity <= 0 or quantity > order.quantity:
            raise serializers.ValidationError(f"Quantity must be a positive number and not exceed your ordered quantity ({order.quantity}).")

        if product.Supplier.user == user:
            raise serializers.ValidationError("You cannot create a return request for your own product.")

        if ReturnRequest.objects.filter(user=user, product=product, order_id=order_id).exists():
            raise serializers.ValidationError("You have already submitted a return request for this product.")
            
        return data

class ReturnRequestListRetrieveSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    product = SimpleProductSerializer(read_only=True)
    status = serializers.CharField(source='get_status_display')
    
    class Meta:
        model = ReturnRequest
        fields = ("id", "user", "from_state", "to_state", "product", "amount", "status", "created_at")

class ReturnRequestDeliverSerializer(serializers.ModelSerializer):
    confirmation_code = serializers.CharField(write_only=True)
    class Meta:
        model = ReturnRequest
        fields = ['confirmation_code']

class BalanceWithdrawRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Balance_Withdraw_Request
        fields = '__all__'
   
class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = transactions
        fields = '__all__'