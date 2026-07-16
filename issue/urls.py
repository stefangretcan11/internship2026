from django.urls import path

from issue.views import CommentViewSet
from rest_framework.routers import DefaultRouter

from .views import IssueViewSet

router = DefaultRouter()
router.register(r"issue", IssueViewSet, basename="issue")

urlpatterns = [
    path('issues/<uuid:issue_pk>/comments/', CommentViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('issues/<uuid:issue_pk>/comments/<uuid:pk>/',
         CommentViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'})),
]

