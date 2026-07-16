from django.urls import path

from issue.views import CommentViewSet

urlpatterns = [
    path('issues/<uuid:issue_pk>/comments/', CommentViewSet.as_view({'get': 'list', 'post': 'create'})),
    path('issues/<uuid:issue_pk>/comments/<uuid:pk>/',
         CommentViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'})),
]
