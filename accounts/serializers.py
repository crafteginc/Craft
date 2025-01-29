from rest_framework import serializers
from .models import Customer, Supplier, Delivery,User,Address
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken, TokenError 
from products.models import Product ,Category
from products.serializers import ProductImageSerializer
from rest_framework import serializers
from .utils import Google, register_social_user
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from orders.models import Order
from django.utils.timezone import now
import re

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name','last_name','PhoneNO','date_joined','Balance']
        read_only_fields = ['Balance','date_joined']

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id','BuildingNO','Street','City','State']

class AccountProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    class Meta:
        model = Product
        fields = ['id','images','ProductName', 'UnitPrice']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data['images']:
            data['images'] = [data['images'][0]]  # Include only the first image
        return data

class CustomerRegistrationSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(style={"input_type": "password"}, write_only=True)
    password = serializers.CharField(style={"input_type": "password"}, write_only=True)
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password', 'password2','PhoneNO')

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("This email is already registered.")
        return email

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"error": "Passwords do not match"})
        if len(attrs['password']) < 8 or not any(char.isdigit() for char in attrs['password']):
            raise serializers.ValidationError({"error": "Password must be at least 8 characters long and contain at least one digit"})
        if not re.match(r'^(010|011|012|015)\d{8}$', str(attrs['PhoneNO'])):
            raise serializers.ValidationError({"error": "number must be in the format 01*********"})
        if User.objects.filter(PhoneNO=attrs['PhoneNO']).exists():
            raise serializers.ValidationError({"error": "Phone number already exists"})
        
        return attrs

    def save(self, **kwargs):
        user = User(
            email=self.validated_data['email'],
            first_name=self.validated_data['first_name'].title(),
            last_name=self.validated_data['last_name'].title(),
            PhoneNO=self.validated_data['PhoneNO'],
            is_customer=True
        )
        user.password = self.validated_data['password']  # Hash the password
        user.save()
        Customer.objects.create(
            user=user
        )
        return user

class CategoreyTitle(serializers.ModelSerializer):
    class Meta:
       model = Category
       fields =('Title')

class SupplierRegistrationSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(style={"input_type": "password"}, write_only=True)
    password = serializers.CharField(style={"input_type": "password"}, write_only=True)
    CategoryTitle = serializers.CharField(required=True)
    ExperienceYears = serializers.IntegerField(required=True)
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password', 'password2','PhoneNO','CategoryTitle','ExperienceYears')  

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("This email is already registered.")
        return email
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"error": "Passwords do not match"})
        if len(attrs['password']) < 8 or not any(char.isdigit() for char in attrs['password']):
            raise serializers.ValidationError({"error": "Password must be at least 8 characters long and contain at least one digit"})
        if not re.match(r'^(010|011|012|015)\d{8}$', str(attrs['PhoneNO'])):
            raise serializers.ValidationError({"error": "number must be in the format 01*********"})
        # Check if PhoneNO already exists in the database
        if User.objects.filter(PhoneNO=attrs['PhoneNO']).exists():
            raise serializers.ValidationError({"error": "Phone number already exists"})
        
        return attrs
    
    def save(self, **kwargs):
        user = User(
            email=self.validated_data['email'],
            first_name=self.validated_data['first_name'].title(),
            last_name=self.validated_data['last_name'].title(),
            PhoneNO=self.validated_data['PhoneNO'],
            is_supplier=True
        )
        user.password = self.validated_data['password']  # Hash the password
        user.save()
        Supplier.objects.create(
           user=user,
           CategoryTitle=self.validated_data['CategoryTitle'],
            ExperienceYears=self.validated_data['ExperienceYears'],
           )
        return user
 
class DeliveryRegistrationSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(style={"input_type": "password"}, write_only=True)
    password = serializers.CharField(style={"input_type": "password"}, write_only=True)
    plateNO = serializers.CharField(required=True)
    VehicleModel = serializers.CharField(required=True)
    governorate = serializers.CharField(max_length=100)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password', 'password2', 'PhoneNO', 'plateNO','VehicleModel','governorate')

    def validate_email(self, value):
        email = value.lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("This email is already registered.")
        return email
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"error": "Passwords do not match"})
        if len(attrs['password']) < 8 or not any(char.isdigit() for char in attrs['password']):
            raise serializers.ValidationError({"error": "Password must be at least 8 characters long and contain at least one digit"})
        if not re.match(r'^(010|011|012|015)\d{8}$', str(attrs['PhoneNO'])):
            raise serializers.ValidationError({"error": "number must be in the format 01*********"})
        # Check if PhoneNO already exists in the database
        if User.objects.filter(PhoneNO=attrs['PhoneNO']).exists():
            raise serializers.ValidationError({"error": "Phone number already exists"})
        
        return attrs
    def save(self, **kwargs):
        user = User(
            email=self.validated_data['email'],
            first_name=self.validated_data['first_name'].title(),
            last_name=self.validated_data['last_name'].title(),
            is_delivery=True
        )
        user.password = self.validated_data['password']  # Hash the password
        user.save()
        Delivery.objects.create(
            user=user,
            plateNO=self.validated_data['plateNO'],
            VehicleModel=self.validated_data['VehicleModel'],
            governorate=self.validated_data['governorate'],
        )
        return user
    
class LoginSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length=155, min_length=6)
    password=serializers.CharField(max_length=68, write_only=True)
    first_name=serializers.CharField(max_length=255, read_only=True)
    access=serializers.CharField(max_length=255, read_only=True)
    refresh=serializers.CharField(max_length=255, read_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'access', 'refresh']


    def validate(self, attrs):
        email = attrs.get('email').lower()
        password = attrs.get('password')
        request=self.context.get('request')
        user = authenticate(request, email=email, password=password)
        if not user:
            raise AuthenticationFailed({"message": "Invalid credentials, try again"})
        if not user.is_verified:
            raise AuthenticationFailed({"message": "Email is not verified"})
        tokens=user.tokens()
        return {
            'email':user.email,
            'first_name':user.first_name,
            "access":str(tokens.get('access')),
            "refresh":str(tokens.get('refresh'))
        }

class CustomerProfileSerializer(serializers.ModelSerializer):
 user = UserSerializer()
 class Meta:
        model = Customer
        fields =  ['user','id','CustomerPhoto']

 def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance   
 def validate(self, attrs):
    # Check if user data is present
    user_data = attrs.get('user')
    if user_data:
        phone_no = str(user_data.get('PhoneNO', ''))
        if not re.match(r'^(010|011|012|015)\d{8}$', phone_no):
            raise serializers.ValidationError({"error": "Phone number must be in the format 01*"})
        # Exclude the current user instance from the query if it exists
        if User.objects.filter(PhoneNO=phone_no).exclude(pk=self.instance.user.pk).exists():
            raise serializers.ValidationError({"error": "Phone number already exists"})
    return attrs

class SupplierProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    products = AccountProductSerializer(many=True, source='product_set')
    orders_created_today = serializers.SerializerMethodField()  # Custom field for daily orders count

    class Meta:
        model = Supplier
        fields = [
            'user', 'id', 'SupplierCover', 'SupplierPhoto', 'CategoryTitle', 
            'ExperienceYears', 'Rating', 'Orders', 'products', 'accepted_supplier', 
            'orders_created_today'  # Add the new field here
        ]
        read_only_fields = ['Orders', 'Rating']

    def get_orders_created_today(self, obj):
        """
        Calculate the number of orders created today for the supplier.
        """
        today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)
        return Order.objects.filter(supplier=obj, created_at__gte=today_start).count()

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    def validate(self, attrs):
        # Check if user data is present
        user_data = attrs.get('user')
        if user_data:
            phone_no = str(user_data.get('PhoneNO', ''))
            if not re.match(r'^(010|011|012|015)\d{8}$', phone_no):
                raise serializers.ValidationError({"error": "Phone number must be in the format 01*"})
            # Exclude the current user instance from the query if it exists
            if User.objects.filter(PhoneNO=phone_no).exclude(pk=self.instance.user.pk).exists():
                raise serializers.ValidationError({"error": "Phone number already exists"})
        return attrs

class deliveryProfileSerializer(serializers.ModelSerializer):
 user = UserSerializer()
 class Meta:
        model = Delivery
        fields =  ['user','id','DeliveryPhoto','Rating','Orders','ExperienceYears','VehicleModel','plateNO']
        read_only_fields = ['Orders','Rating']
 def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        user = instance.user
        for attr, value in user_data.items():
            setattr(user, attr, value)
        user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
 def validate(self, attrs):
    # Check if user data is present
    user_data = attrs.get('user')
    if user_data:
        phone_no = str(user_data.get('PhoneNO', ''))
        if not re.match(r'^(010|011|012|015)\d{8}$', phone_no):
            raise serializers.ValidationError({"error": "Phone number must be in the format 01*"})
        # Exclude the current user instance from the query if it exists
        if User.objects.filter(PhoneNO=phone_no).exclude(pk=self.instance.user.pk).exists():
            raise serializers.ValidationError({"error": "Phone number already exists"})
    return attrs

class CraftersSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    SupplierProducts = AccountProductSerializer(many=True, read_only=True)
    class Meta:
        model = Supplier
        fields = ('id','user', 'CategoryTitle','SupplierPhoto', 'SupplierProducts')

    def get_user(self, obj):
        return {'full_name': obj.user.get_full_name}
    
class EmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)

class SetNewPasswordSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=4, min_length=4, write_only=True)
    new_password = serializers.CharField(max_length=100, min_length=8, write_only=True)
    confirm_password = serializers.CharField(max_length=100, min_length=8, write_only=True)
    class Meta:
        fields = ['otp', 'new_password', 'confirm_password']
        
class LogoutUserSerializer(serializers.Serializer):
    refresh_token=serializers.CharField()

    default_error_message = {
        'bad_token': ('Token is expired or invalid')
    }

    def validate(self, attrs):
        self.token = attrs.get('refresh_token')

        return attrs

    def save(self, **kwargs):
        try:
            token=RefreshToken(self.token)
            token.blacklist()
        except TokenError:
            return self.fail('bad_token')

class GoogleSignInSerializer(serializers.Serializer):
    access_token=serializers.CharField(min_length=6)
    def validate_access_token(self, access_token):
        user_data=Google.validate(access_token)
        try:
            user_data['sub']
            
        except:
            raise serializers.ValidationError("this token has expired or invalid please try again")
        
        if user_data['aud'] != settings.GOOGLE_CLIENT_ID:
                raise AuthenticationFailed('Could not verify user.')

        user_id=user_data['sub']
        email=user_data['email']
        first_name=user_data['given_name']
        last_name=user_data['family_name']
        provider='google'

        return register_social_user(provider, email, first_name, last_name)

class SupplierDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ['SupplierContract', 'SupplierIdentity']
        
class deliveryDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        fields = ['DeliveryContract', 'DeliveryIdentity']