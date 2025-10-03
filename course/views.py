from django.db import transaction
from django.db.models import Q, F, Max

from rest_framework import generics, permissions, serializers, viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, NotFound,MethodNotAllowed
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Course, CourseVideos, Enrollment,Supplier,User

from .serializers import (
    CourseSerializer,
    CourseVideosSerializer,
    SimpleCoursesSerializer,
    OwnCourseSerializer,
)
from .permissions import IsSupplier, IsCustomer
from notifications.services import create_notification_for_user


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

class CoursePermissionMixin:
    def _ensure_course_owner(self, course):
        if course.Supplier_id != self.request.user.supplier.id:
            raise PermissionDenied("You are not allowed to modify this course.")

    def _ensure_video_owner(self, video):
        if video.CourseID.Supplier_id != self.request.user.supplier.id:
            raise PermissionDenied("You are not allowed to perform this action on this video.")

class CourseViewSet(viewsets.ModelViewSet, CoursePermissionMixin):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsSupplier]
    filter_backends = [filters.SearchFilter]
    search_fields = ["CourseTitle", "Description"]

    def list(self, request, *args, **kwargs):
        raise MethodNotAllowed("GET", detail="Listing all courses is not allowed.")
    
    def perform_create(self, serializer):
        supplier = self.request.user.supplier
        course_title = (serializer.validated_data.get("CourseTitle") or "").strip()

        if Course.objects.filter(Supplier=supplier, CourseTitle__iexact=course_title).only("CourseID").exists():
            raise serializers.ValidationError({"CourseTitle": "You already have a course with this name."})

        course = serializer.save(Supplier=supplier)

        # ✨ NOTIFICATION: Inform the supplier that their course has been created
        create_notification_for_user(
            user=self.request.user,
            message=f"Your new course, '{course.CourseTitle}', has been successfully created.",
            related_object=course,
            image=course.Thumbnail
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({"message": "Course created successfully"}, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        self._ensure_course_owner(instance)
        return super().partial_update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        self._ensure_course_owner(instance)
        instance.delete()

    @action(detail=False, methods=["get"], url_path="my-courses")
    def list_own_courses(self, request):
        # ... (rest of the method remains the same)
        pass

class LectureViewSet(viewsets.ModelViewSet, CoursePermissionMixin):
    serializer_class = CourseVideosSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "VideoID"
    queryset = CourseVideos.objects.select_related("CourseID", "CourseID__Supplier")
    filter_backends = [filters.SearchFilter]
    search_fields = ["LectureTitle", "Description"]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # ... (rest of the method remains the same)
        pass

    def perform_create(self, serializer):
        course = serializer.validated_data.get("CourseID")
        if course.Supplier_id != self.request.user.supplier.id:
            raise PermissionDenied("You are not allowed to create videos for this course.")
        
        max_video_no = CourseVideos.objects.filter(CourseID=course).aggregate(Max('VideoNo'))['VideoNo__max']
        new_video_no = (max_video_no or 0) + 1
        video = serializer.save(VideoNo=new_video_no)
        Course.objects.filter(pk=course.pk).update(NumberOfUploadedLec=F("NumberOfUploadedLec") + 1)
        
        enrolled_users = User.objects.filter(enrollment__Course=course)
        for user in enrolled_users:
            create_notification_for_user(
                user=user,
                message=f"A new lecture, '{video.LectureTitle}', has been added to '{course.CourseTitle}'.",
                related_object=course,
                image=course.Thumbnail
            )
        
    def perform_update(self, serializer):
        self._ensure_video_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_video_owner(instance)
        course_id = instance.CourseID_id
        instance.delete()
        Course.objects.filter(pk=course_id).update(NumberOfUploadedLec=F("NumberOfUploadedLec") - 1)

class SimpleCoursesListAPIView(generics.ListAPIView):
    serializer_class = SimpleCoursesSerializer
    filter_backends = [filters.SearchFilter]
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    search_fields = [
        "CourseTitle",
        "Description",
        "Supplier__user__first_name",
        "Supplier__user__last_name",
    ]

    def get_queryset(self):
        queryset = Course.objects.all()
        user = self.request.user
        if hasattr(user, "supplier"):
            queryset = queryset.exclude(Supplier=user.supplier)
        return queryset

class OneCourseDetailAPIView(generics.RetrieveAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        course = self.get_object()

        # allow if user enrolled or course owner
        is_enrolled = Enrollment.objects.filter(Course=course, EnrolledUser=request.user).exists()
        is_owner = hasattr(request.user, "supplier") and (course.Supplier_id == request.user.supplier.id)

        if not (is_enrolled or is_owner):
            raise PermissionDenied("You are not allowed to access this course.")

        return Response(self.get_serializer(course).data)

class CourseLecturesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["LectureTitle", "Description"]
    pagination_class = StandardResultsSetPagination

    def get(self, request, pk):
        try:
            # Attempt to retrieve the Course object by its primary key (pk)
            course = Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            # If the course does not exist, raise a 404 Not Found error
            raise NotFound("Course not found.")

        # Check if the requesting user is the supplier of this course
        is_supplier = False
        try:
            # Try to get the Supplier object linked to the current user
            supplier = Supplier.objects.get(user=request.user)
            # If the course's supplier is the same as the user's supplier, set is_supplier to True
            if course.Supplier == supplier:
                is_supplier = True
        except Supplier.DoesNotExist:
            # If the user is not associated with any supplier, is_supplier remains False
            pass

        # Check if the requesting user is enrolled in this course
        is_enrolled = Enrollment.objects.filter(Course=course, EnrolledUser=request.user).exists()

        # If the user is neither the supplier nor enrolled, deny access
        if not is_supplier and not is_enrolled:
            raise PermissionDenied("You are not allowed to access lectures for this course. You must be either the course supplier or an enrolled user.")

        # If the user has permission (either supplier or enrolled), retrieve all lectures for the course
        lectures = CourseVideos.objects.filter(CourseID=course)
        
        # Serialize the retrieved lectures
        serializer = CourseVideosSerializer(lectures, many=True)
        
        # Return the serialized data
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class EnrolledCoursesAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CourseSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Course.objects.filter(enrollments__EnrolledUser=self.request.user).select_related("Supplier")
