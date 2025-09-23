from django.contrib import admin
from django.urls import path,include
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.conf import settings
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf.urls.i18n import i18n_patterns

schema_view = get_schema_view(
    openapi.Info(
        title="Episyche Technologies API",
        default_version='v1',
        description="API documentation for Craft application",
        terms_of_service="https://www.example.com/policies/terms/",
        contact=openapi.Contact(email="Waleeddarwesh2002@gmail.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

from django.conf.urls.i18n import i18n_patterns

urlpatterns = [
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('product/', include('products.urls')),
    path('course/', include('course.urls')),
    path('orders/', include('orders.urls')),
    path('payment/', include('payment.urls')),
    path('review/', include('reviews.urls')),
    path('notifications/', include('notifications.urls')),
    path('chat/', include('chatapp.urls')),
    path('return/', include('returnrequest.urls')),
    path('reports/', include('reports.urls')),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]

urlpatterns += i18n_patterns(
)

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
