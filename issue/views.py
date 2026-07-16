from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from issue.models import Comment, Issue, IssueReport
from issue.serializers import CommentSerializer
from django.db.models import Q
from users.models import CustomUser
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action

from users.permissions import (
    CanCreateIssue,
    IsAdmin,
    IsIssueOwnerOrAdmin,
    IsCommentOwner
)

from .models import Issue
from .serializers import (
    IssueSerializer,
    IssueUpdateSerializer,
)

STATUS_MESSAGES = {
    'NEW': 'Issue has been created.',
    'DELAYED': 'Issue has been delayed.',
    'IN_PROGRESS': 'Issue is being processed.',
    'DONE': 'Issue has been resolved.',
}


class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        queryset = Issue.objects.select_related(
            "owner",
            "assigned",
            "validator",
        ).order_by("-report_count", "-date_created")


        # Rolurile interne pot vedea toate issues.
        if user.role in {
            CustomUser.Role.ADMIN,
            CustomUser.Role.SUPERADMIN,
            CustomUser.Role.VALIDATOR,
            CustomUser.Role.AGENT,
        }:
            return queryset

        return queryset.filter(
            Q(owner=user) | Q(is_validated=True)
        ).distinct()

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return IssueUpdateSerializer

        return IssueSerializer

    def get_permissions(self):
        if self.action == "create":
            return [
                IsAuthenticated(),
                CanCreateIssue(),
            ]

        if self.action in {"update", "partial_update"}:
            return [
                IsAuthenticated(),
                IsIssueOwnerOrAdmin(),
            ]

        if self.action == "destroy":
            return [
                IsAuthenticated(),
                IsAdmin(),
            ]

        return [
            IsAuthenticated(),
        ]
    @action(detail=True, methods=['post'], url_path='report')
    def report_issue(self, request, pk=None):
        issue = self.get_object()
        report, created = IssueReport.objects.get_or_create(
            issue=issue,
            user=request.user
        )
        if not created:
            return Response(
                {"detail": "You have already reported this issue."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Update the counter
        issue.report_count = issue.reports.count()
        issue.save(update_fields=['report_count'])
        return Response(
            {"detail": "Issue reported.", "report_count": issue.report_count},
            status=status.HTTP_201_CREATED
        )


    def perform_create(self, serializer):
        serializer.save(
            owner=self.request.user,
            status=Issue.Status.NEW,
            is_validated=False,
        )

    def perform_update(self, serializer):
        # only agent/admin can change status
        if 'status' in self.request.data:
            if self.request.user.role not in {'agent', 'admin', 'superadmin'}:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Only agents or admins can change issue status.")
        issue = self.get_object()
        old_status = issue.status
        updated_issue = serializer.save()
        new_status = updated_issue.status
        # auto create comment on status change
        if old_status != new_status:
            message = STATUS_MESSAGES.get(new_status, f'Status changed to {new_status}.')
            Comment.objects.create(
                issue=updated_issue,
                user=self.request.user,
                description=f'Status changed from {old_status} to {new_status}. {message}',
                is_system=True
            )


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    # returns only comments that belong to the issue in the URL
    def get_queryset(self):
        return Comment.objects.filter(issue_id=self.kwargs['issue_pk'])

    def get_permissions(self):
        if self.action == 'partial_update':
            # only the author can edit their comment
            return [IsAuthenticated(), IsCommentOwner()]
        elif self.action == 'destroy':
            # the author or an admin can delete
            return [IsAuthenticated(), IsCommentOwner() | IsAdmin()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        issue_pk = self.kwargs['issue_pk']
        if not Issue.objects.filter(id=issue_pk).exists():
            raise NotFound("Issue not found.")
        serializer.save(user=self.request.user, issue_id=issue_pk)

    def perform_update(self, serializer):
        comment = self.get_object()
        if comment.is_system:
            raise PermissionDenied("System comments cannot be modified.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_system:
            raise PermissionDenied("System comments cannot be deleted.")
        instance.delete()
