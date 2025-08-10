from rest_framework.response import Response
from rest_framework import generics,status,permissions,serializers,viewsets,filters
from .serializers import CourseSerializer,CourseVideosSerializer,SimpleCoursesSerializer
from .models import Course, CourseVideos,Enrollment,Customer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .permissions import IsSupplier,IsCustomer
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet
from django.http import Http404

class CourseAPIView(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsSupplier]

    def perform_create(self, serializer):
        supplier_instance = self.request.user.supplier
        course_name = serializer.validated_data.get('CourseTitle')
        existing_course = Course.objects.filter(CourseTitle=course_name).exists()
        if not existing_course:
            serializer.save(Supplier=supplier_instance)
        else:
            raise serializers.ValidationError({"message":"Course with this name already exists"})
        
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)  
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({"message": "Course created successfully"}, status=status.HTTP_201_CREATED, headers=headers)
    
    def perform_update(self, serializer):
        course = serializer.instance
        if course.Supplier.user != self.request.user:
            raise PermissionDenied("You are not allowed to edit this course.")
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        if instance.Supplier.user != self.request.user:
            raise PermissionDenied("You are not allowed to delete this course.")
        instance.delete()

class LectureListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = CourseVideosSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        CourseID = self.request.query_params.get('CourseID')
        if not CourseID:
            raise Http404({"message":"CourseID not provided."})
        
        if not Course.objects.filter(id=CourseID).exists():
            raise Http404({"message":"Course not found."})

        return CourseVideos.objects.filter(CourseID=CourseID)

    def perform_create(self, serializer):
        course = serializer.validated_data['CourseID']
        if course.Supplier.user != self.request.user:
            raise PermissionDenied("You are not allowed to create videos for this course.")
        serializer.save()

class LectureRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CourseVideos.objects.all()
    serializer_class = CourseVideosSerializer
    permission_classes = [permissions.IsAuthenticated]

    def check_permission(self, instance):
        if instance.CourseID.Supplier.user != self.request.user:
            raise PermissionDenied("You are not allowed to perform this action on this video.")

    def perform_update(self, serializer):
        instance = serializer.instance
        self.check_permission(instance)
        serializer.save()

    def perform_destroy(self, instance):
        self.check_permission(instance)
        instance.delete()

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class SimpleCoursesListAPIView(generics.ListAPIView):
    serializer_class = SimpleCoursesSerializer
    filter_backends = [filters.SearchFilter]
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    search_fields = ['CourseTitle', 'Description', 'Supplier__user__first_name', 'Supplier__user__last_name']
    
    def get_queryset(self):
        queryset = Course.objects.all()
        user = self.request.user

        # If supplier, exclude own courses
        if hasattr(user, 'supplier'):
            queryset = queryset.exclude(Supplier=user.supplier)

        return queryset
    
class OneCourseDetailView(ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated,IsCustomer,IsSupplier]
   
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CourseSerializer
        return self.serializer_class
    
    def get_permissions(self):
        if self.action == 'retrieve':
            return [IsAuthenticated(), IsCustomer(), IsSupplier()]
        elif self.action in ['create','update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsSupplier()]  
        return [IsAuthenticated()]  
    
class CourseLecturesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            course = Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            raise PermissionDenied("Course not found.")

        if not Enrollment.objects.filter(Course=course, EnrolledUser=request.user).exists():
            raise PermissionDenied("You are not allowed to access this course.")

        serializer = CourseSerializer(course)
        return Response(serializer.data)

class EnrolledCoursesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        enrollments = Enrollment.objects.filter(EnrolledUser=request.user)
        courses = [enrollment.Course for enrollment in enrollments]
        serializer = CourseSerializer(courses, many=True)
        return Response(serializer.data)

class EnrollInCourseAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            course = Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            return Response({"message": "Course not found."}, status=404)

        # Prevent enrolling in own course
        if hasattr(request.user, 'supplier') and course.Supplier == request.user.supplier:
            return Response({"message": "You cannot enroll in your own course."}, status=400)

        # Prevent duplicate enrollment
        if Enrollment.objects.filter(Course=course, EnrolledUser=request.user).exists():
            return Response({"message": "Already enrolled in this course."}, status=400)

        Enrollment.objects.create(Course=course, EnrolledUser=request.user)
        return Response({"message": "Enrolled successfully."}, status=201)