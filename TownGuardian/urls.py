from django.contrib import admin
from django.urls import path, re_path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from users.views import (
    CustomTokenObtainPairView,
    ValidateUserView,
    ResetPasswordByEmailView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # auth
    path('auth/jwt/create/', CustomTokenObtainPairView.as_view(), name='jwt-create'),
    re_path(r'^auth/', include('djoser.urls')),
    re_path(r'^auth/', include('djoser.urls.jwt')),

    # validator endpoints
    path('api/users/<int:user_id>/validate/', ValidateUserView.as_view(), name='validate-user'),

    # password reset
    path('auth/reset-password/', ResetPasswordByEmailView.as_view(), name='reset-password'),
]
