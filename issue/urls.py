from django.urls import path

from .views import IssueViewSet
from issue.views import CommentViewSet

urlpatterns = [
    # Issues
    path('issues/',
         IssueViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('issues/<uuid:pk>/',
         IssueViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'})),
    path('issues/<uuid:pk>/report/',
         IssueViewSet.as_view({'post': 'report'})),
    path('issues/<uuid:issue_pk>/comments/',
         CommentViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('issues/<uuid:issue_pk>/comments/<uuid:pk>/',
         CommentViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'})),
]
