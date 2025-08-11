import datetime
from rest_framework import serializers
from course.models import Course
from orders.models import Order
from django.conf import settings

class OrderInformationSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()

    def validate_order_id(self, value):
        try:
            order = Order.objects.get(id=value)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order with the given ID does not exist.")
        
        # Add a check to ensure the order has not already been paid.
        if order.status == 'paid':
            raise serializers.ValidationError("This order has already been paid.")
            
        return value
    
class CourseInformationSerializer(serializers.Serializer):
    course_id = serializers.IntegerField()

    def validate_course_id(self, value):
        try:
            course = Course.objects.get(CourseID=value)
        except Course.DoesNotExist:
            raise serializers.ValidationError("Course with the given ID does not exist.")

        # You might want to add a check for price or other attributes here if needed.

        return value