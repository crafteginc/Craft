from rest_framework import serializers
from .models import Course, CourseVideos, Enrollment
from accounts.serializers import CraftersSerializer

class BaseCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            "CourseID",
            "Thumbnail",
            "CourseTitle",
            "NumberOfLec",
            "completed",
        ]

class CourseSerializer(BaseCourseSerializer):
    Supplier = CraftersSerializer(read_only=True)

    class Meta(BaseCourseSerializer.Meta):
        fields = BaseCourseSerializer.Meta.fields + [
            "CategoryID",
            "Rating",
            "NumberOfRatings",
            "FromDate",
            "ToDate",
            "CourseHours",
            "address",
            "Price",
            "Description",
            "Supplier",
        ]

class OwnCourseSerializer(BaseCourseSerializer):
    SupplierName = serializers.CharField(
        source="Supplier.user.get_full_name", read_only=True
    )
    SupplierPhoto = serializers.ImageField(
        source="Supplier.SupplierPhoto", read_only=True
    )

    class Meta(BaseCourseSerializer.Meta):
        fields = BaseCourseSerializer.Meta.fields + [
            "NumberOfUploadedLec",
            "SupplierName",
            "SupplierPhoto",
        ]

class SimpleCoursesSerializer(BaseCourseSerializer):
    class Meta(BaseCourseSerializer.Meta):
        fields = BaseCourseSerializer.Meta.fields + [
            "CategoryID",
            "Rating",
            "NumberOfRatings",
            "FromDate",
            "address",
            "Price",
        ]

class CourseVideosSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseVideos
        fields = [
            "CourseID",
            "VideoID",
            "VideoNo",
            "LectureTitle",
            "Description",
            "VideoFile",
        ]
        read_only_fields = ("VideoNo",)

class EnrollmentSerializer(serializers.ModelSerializer):
    videos = CourseVideosSerializer(
        source="Course.coursevideos_set", many=True, read_only=True
    )

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "Course",
            "User",
            "EnrollmentDate",
            "videos",
        ]
