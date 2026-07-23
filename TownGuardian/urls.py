from django.contrib import admin
from django.urls import path, re_path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from users.views import (
    CustomTokenObtainPairView,
    ValidateUserView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include("zone.urls")),
    path("api/", include("issue.urls")),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    

    # auth
    path('auth/jwt/create/', CustomTokenObtainPairView.as_view(), name='jwt-create'),
    re_path(r'^auth/', include('djoser.urls')),
    re_path(r'^auth/', include('djoser.urls.jwt')),

    # password reset + users
    re_path(r'^auth/', include('users.urls')),
]
