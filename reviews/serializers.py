from rest_framework import serializers
from .models import Review
from accounts.models import Customer, Delivery, Supplier
from products.models import Product
from course.models import Course

class ReviewSerializer(serializers.ModelSerializer):
    customer = serializers.CharField(default=serializers.CurrentUserDefault(), read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'customer', 'product', 'course', 'delivery', 'supplier',
            'rating', 'comment', 'image', 'ease_of_place_order',
            'speed_of_delivery', 'product_packaging', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication is required to make a review.")

        try:
            customer_instance = Customer.objects.get(user=request.user)
        except Customer.DoesNotExist:
            raise serializers.ValidationError("You must be a customer to make a review.")

        # Determine the object type and ID from the request data
        product_id = request.data.get('product_id')
        course_id = request.data.get('course_id')
        delivery_id = request.data.get('delivery_id')
        supplier_id = request.data.get('supplier_id')

        # Check for mutually exclusive IDs
        provided_ids = [id for id in [product_id, course_id, delivery_id, supplier_id] if id is not None]
        if len(provided_ids) != 1:
            raise serializers.ValidationError("You must provide exactly one of product_id, course_id, delivery_id, or supplier_id.")

        review_target = None
        
        if product_id:
            try:
                review_target = Product.objects.get(pk=product_id)
                if Review.objects.filter(customer=customer_instance, product=review_target).exists():
                    raise serializers.ValidationError("You have already reviewed this product.")
                validated_data['product'] = review_target
            except Product.DoesNotExist:
                raise serializers.ValidationError({"product_id": "Invalid product ID."})
        
        elif course_id:
            try:
                review_target = Course.objects.get(pk=course_id)
                if Review.objects.filter(customer=customer_instance, course=review_target).exists():
                    raise serializers.ValidationError("You have already reviewed this course.")
                validated_data['course'] = review_target
            except Course.DoesNotExist:
                raise serializers.ValidationError({"course_id": "Invalid course ID."})

        elif delivery_id:
            try:
                review_target = Delivery.objects.get(pk=delivery_id)
                if Review.objects.filter(customer=customer_instance, delivery=review_target).exists():
                    raise serializers.ValidationError("You have already reviewed this delivery.")
                validated_data['delivery'] = review_target
            except Delivery.DoesNotExist:
                raise serializers.ValidationError({"delivery_id": "Invalid delivery ID."})
        
        elif supplier_id:
            try:
                review_target = Supplier.objects.get(pk=supplier_id)
                if Review.objects.filter(customer=customer_instance, supplier=review_target).exists():
                    raise serializers.ValidationError("You have already reviewed this supplier.")
                validated_data['supplier'] = review_target
            except Supplier.DoesNotExist:
                raise serializers.ValidationError({"supplier_id": "Invalid supplier ID."})
        
        return Review.objects.create(customer=customer_instance, **validated_data)

    def update(self, instance, validated_data):
        instance.rating = validated_data.get('rating', instance.rating)
        instance.comment = validated_data.get('comment', instance.comment)
        instance.image = validated_data.get('image', instance.image)
        instance.ease_of_place_order = validated_data.get('ease_of_place_order', instance.ease_of_place_order)
        instance.speed_of_delivery = validated_data.get('speed_of_delivery', instance.speed_of_delivery)
        instance.product_packaging = validated_data.get('product_packaging', instance.product_packaging)
        instance.save()
        return instance