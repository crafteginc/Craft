from django.db import transaction
from django.db.models import Q, F

from rest_framework import generics, permissions, serializers, viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Course, CourseVideos, Enrollment
from .serializers import (
    CourseSerializer,
    CourseVideosSerializer,
    SimpleCoursesSerializer,
    OwnCourseSerializer,
)
from .permissions import IsSupplier, IsCustomer

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

    def perform_create(self, serializer):
        supplier = self.request.user.supplier
        course_title = (serializer.validated_data.get("CourseTitle") or "").strip()

        if Course.objects.filter(Supplier=supplier, CourseTitle__iexact=course_title).only("CourseID").exists():
            raise serializers.ValidationError({"CourseTitle": "You already have a course with this name."})

        serializer.save(Supplier=supplier)

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
        supplier = request.user.supplier
        queryset = Course.objects.filter(Supplier=supplier).order_by("-CourseID")

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(CourseTitle__icontains=search) |
                Q(Description__icontains=search)
            )

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = OwnCourseSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)
    
class LectureViewSet(viewsets.ModelViewSet, CoursePermissionMixin):
    serializer_class = CourseVideosSerializer
    permission_classes = [IsAuthenticated]
    queryset = CourseVideos.objects.select_related("CourseID", "CourseID__Supplier")
    filter_backends = [filters.SearchFilter]
    search_fields = ["Title", "Description"]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if self.action == "list":
            course_id = self.request.query_params.get("CourseID")
            if not course_id:
                raise NotFound("CourseID not provided.")

            try:
                course = Course.objects.get(pk=course_id)
            except Course.DoesNotExist:
                raise NotFound("Course not found.")

            return self.queryset.filter(CourseID=course)

        return self.queryset

    @transaction.atomic
    def perform_create(self, serializer):
        course = serializer.validated_data.get("CourseID")
        if course.Supplier_id != self.request.user.supplier.id:
            raise PermissionDenied("You are not allowed to create videos for this course.")

        serializer.save()

        Course.objects.filter(pk=course.pk).update(NumberOfUploadedLec=F("NumberOfUploadedLec") + 1)

    @transaction.atomic
    def perform_update(self, serializer):
        self._ensure_video_owner(serializer.instance)
        serializer.save()

    @transaction.atomic
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

    def get(self, request, pk):
        try:
            course = Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            raise NotFound("Course not found.")

        if not Enrollment.objects.filter(Course=course, EnrolledUser=request.user).exists():
            raise PermissionDenied("You are not allowed to access this course.")

        serializer = CourseSerializer(course)
        return Response(serializer.data)

class EnrolledCoursesAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CourseSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        return Course.objects.filter(enrollment__EnrolledUser=self.request.user).select_related("Supplier")
