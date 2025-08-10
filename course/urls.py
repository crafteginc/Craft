from django.urls import path, include
from rest_framework import routers
from .views import (
    CourseAPIView,
    LectureListCreateAPIView,
    LectureRetrieveUpdateDestroyAPIView,
    CourseLecturesAPIView,
    SimpleCoursesListAPIView,
    OneCourseDetailView,
    EnrolledCoursesAPIView,
    EnrollInCourseAPIView
)

# Router setup
router = routers.DefaultRouter()
router.register(r'courses', CourseAPIView, basename='course-create')
router.register(r'course-detail', OneCourseDetailView, basename='course-detail')

urlpatterns = [
    # Router URLs
    path('', include(router.urls)),

    # Courses
    path('courses-list/', SimpleCoursesListAPIView.as_view(), name='all-courses-list'),
    path('user/courses/', EnrolledCoursesAPIView.as_view(), name='user-courses-list'),
    path('courses/<int:pk>/enroll/', EnrollInCourseAPIView.as_view(), name='enroll-course'),
    # Lectures
    path('lecture/', LectureListCreateAPIView.as_view(), name='lecture-create'),
    path('lecture/<int:pk>/', LectureRetrieveUpdateDestroyAPIView.as_view(), name='lecture-retrieve-update-destroy'),
    path('course-lectures/<int:CourseID>/', CourseLecturesAPIView.as_view(), name='course-lectures'),
]
