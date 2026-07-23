from django.urls import path, include
from rest_framework.routers import DefaultRouter

from issue.views import (
    AgentAvailabilityView,
    AlertViewSet,
    CommentViewSet,
    IssueViewSet,
    IssueStatisticsView,
)

router = DefaultRouter()
router.register(r'issues', IssueViewSet, basename='issue')
router.register(r'alerts', AlertViewSet, basename='alert')

urlpatterns = [
    path('dashboard/agents-availability/', AgentAvailabilityView.as_view()),
    path('statistics/issues/', IssueStatisticsView.as_view()),
    path('issues/<uuid:issue_pk>/comments/', CommentViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('issues/<uuid:issue_pk>/comments/<uuid:pk>/', CommentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'})),
    path('', include(router.urls)),
]
