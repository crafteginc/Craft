from django.db.models import F, Max, Prefetch
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache

from rest_framework import generics, permissions, filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Course, CourseVideos, Enrollment, Supplier, User
from .serializers import CourseSerializer, CourseVideosSerializer, SimpleCoursesSerializer
from .permissions import IsSupplier
from notifications.services import create_notification_for_user
from .tasks import create_course_task



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
    queryset = Course.objects.select_related("Supplier", "Supplier__user").only(
        "id", "CourseTitle", "Description", "Thumbnail", "Supplier_id", "NumberOfUploadedLec"
    )
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated, IsSupplier]
    filter_backends = [filters.SearchFilter]
    search_fields = ["CourseTitle", "Description"]

    # Cache list view for 15 min (public cache)
    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    # Cache detail view per-course for 15 min
    @method_decorator(cache_page(60 * 15))
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Offload course creation to Celery to avoid DB lock
        create_course_task.delay(request.user.id, serializer.validated_data)

        return Response(
            {"message": "Your course is being created and will be available shortly."},
            status=status.HTTP_202_ACCEPTED,
        )

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        self._ensure_course_owner(instance)
        return super().partial_update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        self._ensure_course_owner(instance)
        instance.delete()

    @action(detail=False, methods=["get"], url_path="my-courses")
    def list_own_courses(self, request):
        supplier = getattr(request.user, "supplier", None)
        if not supplier:
            raise PermissionDenied("You are not a supplier.")
        queryset = self.get_queryset().filter(Supplier=supplier)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class LectureViewSet(viewsets.ModelViewSet, CoursePermissionMixin):
    serializer_class = CourseVideosSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "VideoID"
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["LectureTitle", "Description"]

    queryset = CourseVideos.objects.select_related(
        "CourseID", "CourseID__Supplier", "CourseID__Supplier__user"
    ).only("VideoID", "LectureTitle", "Description", "CourseID_id")

    def perform_create(self, serializer):
        course = serializer.validated_data["CourseID"]

        if course.Supplier_id != self.request.user.supplier.id:
            raise PermissionDenied("You are not allowed to create videos for this course.")

        # Use annotation + F to avoid multiple queries
        max_video_no = CourseVideos.objects.filter(CourseID=course).aggregate(Max("VideoNo"))["VideoNo__max"]
        new_video_no = (max_video_no or 0) + 1

        video = serializer.save(VideoNo=new_video_no)

        Course.objects.filter(pk=course.pk).update(
            NumberOfUploadedLec=F("NumberOfUploadedLec") + 1
        )

        # Prefetch enrolled users efficiently
        enrolled_users = User.objects.filter(
            enrollment__Course=course
        ).only("id", "email", "first_name")

        # Send notification efficiently (batched)
        for user in enrolled_users.iterator():
            create_notification_for_user(
                user=user,
                message=f"A new lecture, '{video.LectureTitle}', has been added to '{course.CourseTitle}'.",
                related_object=course,
                image=course.Thumbnail,
            )

    def perform_update(self, serializer):
        self._ensure_video_owner(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self._ensure_video_owner(instance)
        course_id = instance.CourseID_id
        instance.delete()
        Course.objects.filter(pk=course_id).update(
            NumberOfUploadedLec=F("NumberOfUploadedLec") - 1
        )


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
        queryset = (
            Course.objects.select_related("Supplier", "Supplier__user")
            .only("id", "CourseTitle", "Description", "Thumbnail", "Supplier_id")
        )
        user = self.request.user
        if hasattr(user, "supplier"):
            queryset = queryset.exclude(Supplier=user.supplier)
        return queryset


class OneCourseDetailAPIView(generics.RetrieveAPIView):
    queryset = Course.objects.select_related("Supplier", "Supplier__user")
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    @method_decorator(cache_page(60 * 10))
    def get(self, request, *args, **kwargs):
        course = self.get_object()

        # Cache enrollment check for 10 min (reduces repetitive DB hits)
        cache_key = f"user:{request.user.id}:enrolled:{course.id}"
        is_enrolled = cache.get(cache_key)
        if is_enrolled is None:
            is_enrolled = Enrollment.objects.filter(
                Course=course, EnrolledUser=request.user
            ).exists()
            cache.set(cache_key, is_enrolled, 600)

        is_owner = hasattr(request.user, "supplier") and (
            course.Supplier_id == request.user.supplier.id
        )

        if not (is_enrolled or is_owner):
            raise PermissionDenied("You are not allowed to access this course.")

        return Response(self.get_serializer(course).data)


class CourseLecturesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @method_decorator(cache_page(60 * 5))
    def get(self, request, pk):
        try:
            course = Course.objects.only("id", "Supplier_id").get(pk=pk)
        except Course.DoesNotExist:
            raise NotFound("Course not found.")

        # Efficient permission check
        is_supplier = getattr(request.user, "supplier", None)
        if is_supplier and is_supplier.id == course.Supplier_id:
            allowed = True
        else:
            allowed = Enrollment.objects.filter(
                Course=course, EnrolledUser=request.user
            ).exists()

        if not allowed:
            raise PermissionDenied(
                "You are not allowed to access lectures for this course."
            )

        # Optimize lecture query
        lectures = CourseVideos.objects.filter(CourseID=course).only(
            "VideoID", "LectureTitle", "Description", "CourseID_id"
        )

        serializer = CourseVideosSerializer(lectures, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EnrolledCoursesAPIView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CourseSerializer
    pagination_class = StandardResultsSetPagination

    @method_decorator(cache_page(60 * 15))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
