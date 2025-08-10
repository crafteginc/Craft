from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CourseViewSet,
    LectureViewSet,
    SimpleCoursesListAPIView,
    OneCourseDetailAPIView,
    CourseLecturesAPIView,
    EnrolledCoursesAPIView,
)

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="courses")
router.register(r"lectures", LectureViewSet, basename="lectures")

urlpatterns = [
    path("", include(router.urls)),

    # Public / user-specific course lists
    path("simple-courses/", SimpleCoursesListAPIView.as_view(), name="simple-courses"),
    path("enrolled-courses/", EnrolledCoursesAPIView.as_view(), name="enrolled-courses"),

    # Single course detail with permission check
    path("courses/<int:pk>/detail/", OneCourseDetailAPIView.as_view(), name="course-detail"),

    # Lectures for enrolled students
    path("courses/<int:pk>/lectures/", CourseLecturesAPIView.as_view(), name="course-lectures"),
]
