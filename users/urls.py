from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ValidateUserView, UserManagementViewSet,MeView
router = DefaultRouter()
router.register('admin/users', UserManagementViewSet, basename='user-management')
urlpatterns = [
    path('', include(router.urls)),
    path('<int:user_id>/validate/', ValidateUserView.as_view(), name='validate-user'),
    path('me/', MeView.as_view(), name='me'),


]
