from django.http import Http404
from django.shortcuts import get_object_or_404
from .permissions import IsCustomerorSupplier
from . import permissions
from .serializers import CustomerRegistrationSerializer,SupplierRegistrationSerializer,DeliveryRegistrationSerializer,AddressSerializer
from .serializers import LoginSerializer,SetNewPasswordSerializer,LogoutUserSerializer
from .serializers import CustomerProfileSerializer,deliveryProfileSerializer,SupplierProfileSerializer,CraftersSerializer,SupplierDocumentSerializer,deliveryDocumentSerializer
from .utils import send_generated_otp_to_email
from rest_framework.generics import GenericAPIView,ListAPIView
from rest_framework.response import Response
from rest_framework import status ,viewsets
from .utils import OneTimePassword
from rest_framework.permissions import IsAuthenticated
from .models import User,Supplier,Customer,Delivery,Follow,Address
from rest_framework.views import APIView 
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.http import FileResponse
from django.utils.timezone import now, timedelta
from .serializers import EmailVerificationSerializer
from django.core.mail import EmailMessage
import random
from django.conf import settings
from .models import User, OneTimePassword
from .serializers import GoogleSignInSerializer
from asgiref.sync import sync_to_async
from django.contrib.contenttypes.models import ContentType

class ResendOtp(GenericAPIView):
    serializer_class = EmailVerificationSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid(raise_exception=True):
            email = serializer.validated_data['email']

        # Check if the user exists
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            otp = random.randint(1000, 9999)
            OneTimePassword.objects.update_or_create(user=user, defaults={'otp': otp})

            # Check if the user is verified
            if user.is_verified:
                # Email for password reset
                subject = "One-Time Passcode for Password Reset"
                email_body = (
                    f"Hi {user.first_name},\n\n"
                    f"You requested to reset your password.\n\n"
                    f"Use the following OTP to reset it: {otp}\n\n"
                    f"If you did not request this, please ignore this email.\n\n"
                    f"Best regards,\n"
                    f"The CraftEG Team"
                )
            else:
                # Email for email verification
                subject = "One-Time Passcode for Email Verification"
                email_body = (
                    f"Dear {user.first_name},\n\n"
                    f"Thank you for signing up with CraftEG. To complete your registration, please verify your email address using the one-time passcode below:\n\n"
                    f"One-Time Passcode: {otp}\n\n"
                    f"If you did not sign up for a CraftEG account, please disregard this message.\n\n"
                    f"Best regards,\n"
                    f"The CraftEG Team"
                )

            # Send email
            from_email = settings.EMAIL_HOST_USER
            to_email = [user.email]
            email = EmailMessage(subject, email_body, from_email, to_email)
            email.send()

            user.save()
            return Response({"message": "OTP sent to your email."}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "Email not found."}, status=status.HTTP_404_NOT_FOUND)

class RegisterViewforCustomer(GenericAPIView):
    serializer_class = CustomerRegistrationSerializer
    def post(self, request):
        user = request.data        
        serializer = self.serializer_class(data=user)
        if serializer.is_valid():
            serializer.save()
            user_data = serializer.data
            send_generated_otp_to_email(user_data['email'], request)
            return Response({
                'email':user_data['email'],
                'message': 'Thanks for signing up! A passcode has been sent to verify your email.'
            }, status=status.HTTP_201_CREATED)
        
        errors = [msg for error_list in serializer.errors.values() for msg in error_list]
        return Response({'message': errors}, status=status.HTTP_400_BAD_REQUEST)

class RegisterViewforSupplier(GenericAPIView):
    serializer_class = SupplierRegistrationSerializer
    
    def post(self, request):
        user = request.data
        serializer = self.serializer_class(data=user)
        if serializer.is_valid():
            serializer.save()
            user_data = serializer.data
            send_generated_otp_to_email(user_data['email'], request)
            return Response({
                'email':user_data['email'],
                'message': 'Thanks for signing up! A passcode has been sent to verify your email.'
            }, status=status.HTTP_201_CREATED)
        
        errors = [msg for error_list in serializer.errors.values() for msg in error_list]
        return Response({'message': errors}, status=status.HTTP_400_BAD_REQUEST)

class RegisterViewforDelivery(GenericAPIView):
    serializer_class =DeliveryRegistrationSerializer
    def post(self, request):
        user = request.data
        serializer=self.serializer_class(data=user)
        if serializer.is_valid():
            serializer.save()
            user_data=serializer.data
            send_generated_otp_to_email(user_data['email'], request)
            return Response({
                'email':user_data['email'],
                'message':'thanks for signing up a passcode has be sent to verify your email'
            }, status=status.HTTP_201_CREATED)
        errors = [msg for error_list in serializer.errors.values() for msg in error_list]
        return Response({'message': errors}, status=status.HTTP_400_BAD_REQUEST)
    
class VerifyUserEmail(GenericAPIView):
    def post(self, request):
        try:
            # Extract input data
            passcode = request.data.get('otp')
            email = request.data.get('email')

            if not passcode or not email:
                return Response(
                    {'message': 'Both email and OTP are required.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate OTP and email
            user_pass_obj = OneTimePassword.objects.filter(otp=passcode, user__email=email).first()

            if not user_pass_obj:
                return Response(
                    {'message': 'Invalid OTP or email provided.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = user_pass_obj.user

            if user.is_verified:
                return Response(
                    {'message': 'User is already verified.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Mark user as verified
            user.is_verified = True
            user.save()

            # Authenticate the user to generate tokens
            if not user.check_password(request.data.get('password', '')):
                return Response(
                    {'message': 'Invalid password provided.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            tokens = user.tokens()
            user_pass_obj.delete()
            return Response(
                {
                    'message': 'Account email verified and logged in successfully.',
                    'email': user.email,
                    'first_name': user.first_name,
                    'access': str(tokens.get('access')),
                    'refresh': str(tokens.get('refresh'))
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'message': f'An error occurred: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LoginUserView(GenericAPIView):
    serializer_class=LoginSerializer
    def post(self, request):
        serializer= self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class CustomerProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get_object(self, user):
        try:
            return Customer.objects.get(user=user)
        except Customer.DoesNotExist:
            raise Http404("Customer does not exist ")
        
    def get(self, request, format=None):
        customer = self.get_object(request.user)
        serializer = CustomerProfileSerializer(customer)
        return Response(serializer.data)
    
    def patch(self, request, format=None):
        customer = self.get_object(request.user)
        serializer = CustomerProfileSerializer(customer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        errors = [msg for error_list in serializer.errors.values() for msg in error_list]
        return Response({'message': errors}, status=status.HTTP_400_BAD_REQUEST)

class SupplierProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get_object(self, user):
        try:
            return Supplier.objects.get(user=user)
        except Supplier.DoesNotExist:
            raise Http404("SupplierProfile does not exist ")
    def get(self, request, format=None):
        supplier = self.get_object(request.user)
        serializer = SupplierProfileSerializer(supplier)
        return Response(serializer.data)

    def patch(self, request, format=None):
        supplier = self.get_object(request.user)
        serializer = SupplierProfileSerializer(supplier, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        errors = [msg for error_list in serializer.errors.values() for msg in error_list]
        return Response({'message': errors}, status=status.HTTP_400_BAD_REQUEST)

class DeliveryProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get_object(self, user):
        try:
            return Delivery.objects.get(user=user)
        except Delivery.DoesNotExist:
            raise Http404("Delivery Profile does not exist ")
                   
    def get(self, request, format=None):
        delivery = self.get_object(request.user)
        serializer = deliveryProfileSerializer(delivery)
        return Response(serializer.data)
        
    def patch(self, request, format=None):
        delivery = self.get_object(request.user)
        serializer = deliveryProfileSerializer(delivery, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        errors = [msg for error_list in serializer.errors.values() for msg in error_list]
        return Response({'message': errors}, status=status.HTTP_400_BAD_REQUEST)
    
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class SuppliersList(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CraftersSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['CategoryTitle', 'Rating', 'ExperienceYears']
    search_fields = ['user__first_name', 'user__last_name']
    ordering_fields = ['user_first_name']
    pagination_class = StandardResultsSetPagination

    def get_serializer_context(self):
        return {'request': self.request}

    def get_queryset(self):
        # Exclude the logged-in user from the queryset
        user = self.request.user
        return Supplier.objects.filter(user__is_verified=True, user__is_active=True).exclude(user=user).order_by('id')

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)

        # Get the current user
        user = request.user
        
        transformed_data = []
        for supplier in response.data.get('results', []):
            if isinstance(supplier, dict):
                supplier_id = supplier.get('id', '')

                # Check if the current user follows the supplier using follower.id
                # Determine the follower object type (Customer or Supplier)
                if hasattr(user, 'customer'):  # If user is a customer
                    follower_content_type = ContentType.objects.get_for_model(Customer)
                    follower_object_id = user.customer.id
                elif hasattr(user, 'supplier'):  # If user is a supplier
                    follower_content_type = ContentType.objects.get_for_model(Supplier)
                    follower_object_id = user.supplier.id
                else:
                    continue  # If the user is neither a customer nor supplier, skip this user

                # Check if the user follows the supplier
                is_followed = Follow.objects.filter(
                    follower_content_type=follower_content_type,
                    follower_object_id=follower_object_id,  # Using follower.id
                    supplier=supplier_id
                ).exists()

                # Add the `followed_by_user` key
                transformed_supplier = {
                    "id": supplier_id,
                    'full_name': supplier['user']['full_name'] if 'user' in supplier else '',
                    'SupplierPhoto': supplier.get('SupplierPhoto', ''),
                    'CategoryTitle': supplier.get('CategoryTitle', ''),
                    'followed_by_user': is_followed  # Add this line to include follow status
                }

                transformed_data.append(transformed_supplier)
            else:
                print(f"Invalid supplier data: {supplier}")

        return Response(transformed_data)

class TrendingSuppliersAPIView(APIView):
    permission_classes = [IsCustomerorSupplier] 
    def get(self, request, format=None):
        trending_suppliers = Supplier.objects.filter(user__is_verified=True, user__is_active=True).order_by('-Rating','-Orders')[:10]  # Fetch top 10 suppliers based on rating
        serializer = CraftersSerializer(trending_suppliers, many=True)
        return Response(serializer.data)
    
class SupplierDetail(APIView):
    def get(self, request, pk):
        supplier = get_object_or_404(Supplier, pk=pk)

        # Get the current user
        user = request.user

        # Determine the follower content type dynamically based on user type
        if hasattr(user, 'customer'):  # If the user is a Customer
            follower = user.customer
            follower_content_type = ContentType.objects.get_for_model(Customer)
            follower_id = follower.id
        elif hasattr(user, 'supplier'):  # If the user is a Supplier
            follower = user.supplier
            follower_content_type = ContentType.objects.get_for_model(Supplier)
            follower_id = follower.id
        else:
            return Response({'message': 'User must be a customer or supplier'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the current user follows the supplier
        is_followed = Follow.objects.filter(
            follower_content_type=follower_content_type,
            follower_object_id=follower_id,
            supplier=supplier
        ).exists()

        # Debug: Check the query being made
        print(f"Checking follow relationship: User {follower_id} -> Supplier {supplier.id} -> Follow exists: {is_followed}")

        # Transform the data to include only the desired fields for the supplier
        transformed_supplier = {
            "id": supplier.id,
            'full_name': supplier.user.get_full_name,
            'SupplierPhoto': supplier.SupplierPhoto.url if supplier.SupplierPhoto else None,
            'SupplierCover': supplier.SupplierCover.url if supplier.SupplierCover else None,
            'CategoryTitle': supplier.CategoryTitle,
            'ExperienceYears': supplier.ExperienceYears,
            'Orders': supplier.Orders,
            'Rating': supplier.Rating,
            'followed_by_user': is_followed,  # Add this field to indicate if the user follows the supplier
            'SupplierProducts': [
                {
                    'id': product.id,
                    'photo': product.images.first().image.url if product.images.first() else None,
                    'ProductName': product.ProductName,
                    'UnitPrice': product.UnitPrice,
                } for product in supplier.product_set.all()
            ]
        }

        return Response(transformed_supplier, status=status.HTTP_200_OK)

class FollowSupplier(APIView):
    def post(self, request, supplier_id):
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            user = request.user
            
            if hasattr(user, 'customer'):  # If user is a customer
                follower = user.customer
            elif hasattr(user, 'supplier'):  # If user is a supplier
                follower = user.supplier
            else:
                return Response({'message': 'User must be a customer or supplier'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if the supplier is trying to follow themselves
            if isinstance(follower, Supplier) and follower == supplier:
                return Response({'message': 'A supplier cannot follow themselves'}, status=status.HTTP_400_BAD_REQUEST)
            
            follower_content_type = ContentType.objects.get_for_model(follower)
            follow_exists = Follow.objects.filter(
                follower_content_type=follower_content_type,
                follower_object_id=follower.id,
                supplier=supplier
            ).exists()
            
            if follow_exists:
                return Response({'message': 'You have already followed this supplier'}, status=status.HTTP_400_BAD_REQUEST)
            
            Follow.objects.create(
                follower_content_type=follower_content_type,
                follower_object_id=follower.id,
                supplier=supplier
            )
            return Response({'message': 'Followed'}, status=status.HTTP_201_CREATED)
        
        except Supplier.DoesNotExist:
            return Response({'message': 'Supplier not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, supplier_id):
        try:
            supplier = Supplier.objects.get(id=supplier_id)
            user = request.user

            if hasattr(user, 'customer'):
                follower = user.customer
            elif hasattr(user, 'supplier'):
                follower = user.supplier
            else:
                return Response({'message': 'User must be a customer or supplier'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the supplier is trying to unfollow themselves
            if isinstance(follower, Supplier) and follower == supplier:
                return Response({'message': 'A supplier cannot unfollow themselves'}, status=status.HTTP_400_BAD_REQUEST)

            follower_content_type = ContentType.objects.get_for_model(follower)
            follow = Follow.objects.get(
                follower_content_type=follower_content_type,
                follower_object_id=follower.id,
                supplier=supplier
            )
            follow.delete()
            return Response({'message': 'Unfollowed'}, status=status.HTTP_200_OK)
        
        except Supplier.DoesNotExist:
            return Response({'message': 'Supplier not found'}, status=status.HTTP_404_NOT_FOUND)
        except Follow.DoesNotExist:
            return Response({'message': 'You are not following this supplier'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
      
class PasswordResetRequestView(APIView):
    serializer_class = EmailVerificationSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            if user.last_password_reset_request is not None and now() - user.last_password_reset_request < timedelta(minutes=1):
                return Response({"message": "Please wait 1 minute before attempting another password reset."}, status=status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Generate OTP
            otp = random.randint(1000, 9999)
            OneTimePassword.objects.update_or_create(user=user, defaults={'otp': otp})

            # Email content
            subject = "One-Time Passcode for Password Reset"
            email_body = (
                f"Hi {user.first_name},\n\n"
                f"You requested to reset your password. Use the following OTP to reset it:\n\n"
                f"{otp}\n\n"
                f"If you did not request this, please ignore this email.\n\n"
                f"Best regards,\n"
                f"Craft EG Team"
            )
            from_email = settings.EMAIL_HOST_USER
            to_email = [user.email]
            
            # Send email
            try:
                send = EmailMessage(subject, email_body, from_email, to_email)
                send.send()
            except Exception as e:
                return Response({"message": "Failed to send email. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Update last password reset request time
            user.last_password_reset_request = now()
            user.save()

            return Response({"message": "OTP sent to your email for password reset."}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "User with that email does not exist."}, status=status.HTTP_404_NOT_FOUND)

class CheckOTPValidity(APIView):
    def post(self, request):
        try:
            # Retrieve the input data
            otp = request.data.get('otp')
            email = request.data.get('email')

            # Validate input data
            if not otp or not email:
                return Response(
                    {'message': 'Both email and OTP are required.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if the OTP is valid for the provided email
            otp_obj = OneTimePassword.objects.filter(otp=otp, user__email=email).first()

            if not otp_obj:
                return Response(
                    {'message': 'Invalid OTP or email provided.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # If the OTP is valid, return a success message
            return Response(
                {'message': 'OTP is valid.'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'message': f'An error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SetNewPasswordView(APIView):
    serializer_class = SetNewPasswordSerializer
    def patch(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']
        confirm_password = serializer.validated_data['confirm_password']

        if new_password != confirm_password:
            return Response({"message": "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        otp_record = OneTimePassword.objects.filter(otp=otp).first()

        if not otp_record:
            return Response({"message": "Invalid OTP or OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

        user = otp_record.user
        user.set_password(new_password)
        user.save()

        otp_record.delete()  # Delete OTP record after successful password reset

        return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)
    
class LogoutApiView(GenericAPIView):
    serializer_class=LogoutUserSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer=self.serializer_class(data=request.data)
        serializer.is_valid()
        serializer.save()
        return Response({'message': 'Logged Out'},status=status.HTTP_204_NO_CONTENT)

class GoogleOauthSignInview(GenericAPIView):
    serializer_class=GoogleSignInSerializer

    def post(self, request):
        print(request.data)
        serializer=self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data=((serializer.validated_data)['access_token'])
        return Response(data, status=status.HTTP_200_OK) 

class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Address.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)

class SupplierDocumentViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Provide the contract for download
        file_path = 'contract/contract_temp.pdf'
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='contract_template.pdf')

    def create(self, request):
        try:
            supplier = request.user.supplier
        except Supplier.DoesNotExist:
            return Response({'error': 'Supplier profile does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        # Null file checks
        contract = request.FILES.get('SupplierContract')
        identity = request.FILES.get('SupplierIdentity')

        if not contract:
            return Response({'error': 'SupplierContract file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not identity:
            return Response({'error': 'SupplierIdentity file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SupplierDocumentSerializer(supplier, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        errors = [msg for error_list in serializer.errors.values() for msg in error_list]
        return Response({'message': errors}, status=status.HTTP_400_BAD_REQUEST)

class deliveryDocumentViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        # Provide the contract for download
        file_path = 'contract/contract_temp.pdf'
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename='contract_template.pdf')

    def create(self, request):
        try:
            delivery = request.user.delivery
        except Delivery.DoesNotExist:
            return Response({'message': 'Delivery profile does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        # Null checks for required files
        license_file = request.FILES.get('DeliveryLicense')
        identity_file = request.FILES.get('DeliveryIdentity')

        if not license_file:
            return Response({'error': 'DeliveryLicense file is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if not identity_file:
            return Response({'error': 'DeliveryIdentity file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = deliveryDocumentSerializer(delivery, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        errors = [msg for error_list in serializer.errors.values() for msg in error_list]
        return Response({'message': errors}, status=status.HTTP_400_BAD_REQUEST)