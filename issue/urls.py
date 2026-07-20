from django.urls import path

from issue.views import (
    AlertViewSet,
    CommentViewSet,
    IssueViewSet,
)

urlpatterns = [
    # Issues
    path(
        "issues/",
        IssueViewSet.as_view(
            {
                "get": "list",
                "post": "create",
            }
        ),
    ),
    path(
        "issues/nearby/",
        IssueViewSet.as_view(
            {
                "get": "nearby_validated_issues",
            }
        ),
    ),
    path(
        "issues/<uuid:pk>/",
        IssueViewSet.as_view(
            {
                "get": "retrieve",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
    ),
    path(
        "issues/<uuid:pk>/report/",
        IssueViewSet.as_view(
            {
                "post": "report_issue",
            }
        ),
    ),
    path(
        "issues/<uuid:pk>/validated/",
        IssueViewSet.as_view(
            {
                "put": "validated",
            }
        ),
    ),
    path(
        "issues/<uuid:pk>/rejected/",
        IssueViewSet.as_view(
            {
                "put": "rejected",
            }
        ),
    ),
    path(
        "issues/<uuid:pk>/incomplete/",
        IssueViewSet.as_view(
            {
                "put": "incomplete",
            }
        ),
    ),
    path(
        "issues/<uuid:pk>/pending/",
        IssueViewSet.as_view(
            {
                "put": "pending",
            }
        ),
    ),
    path(
        "issues/<uuid:pk>/assign/",
        IssueViewSet.as_view(
            {
                "patch": "assign",
            }
        ),
    ),

    # Comments
    path(
        "issues/<uuid:issue_pk>/comments/",
        CommentViewSet.as_view(
            {
                "get": "list",
                "post": "create",
            }
        ),
    ),
    path(
        "issues/<uuid:issue_pk>/comments/<uuid:pk>/",
        CommentViewSet.as_view(
            {
                "get": "retrieve",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
    ),
    # Alerts
    path(
        "alerts/",
        AlertViewSet.as_view(
            {
                "get": "list",
                "post": "create",
            }
        ),
    ),
    path(
        "alerts/<uuid:pk>/",
        AlertViewSet.as_view(
            {
                "get": "retrieve",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
    ),
    path(
        "alerts/<uuid:pk>/seen/",
        AlertViewSet.as_view(
            {
                "put": "mark_seen",
            }
        ),
    ),
    path(
        "alert/stream/",
        AlertViewSet.as_view(
            {
                "get": "stream",
            }
        ),
    ),
    path(
        "alerts/unseen_count/",
        AlertViewSet.as_view(
            {
                "get": "unseen_count",
            }
        ),
    ),
    path(
        "alerts/mark_all_seen/",
        AlertViewSet.as_view(
            {
                "put": "mark_all_seen",
            }
        ),
    ),

]
