from rest_framework.exceptions import PermissionDenied
from rest_framework import viewsets
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated

from issue.models import Comment, Issue
from issue.serializers import CommentSerializer
from users.permissions import IsCommentOwner, IsAdmin

STATUS_MESSAGES = {
    'NEW': 'Issue has been created.',
    'DELAYED': 'Issue has been delayed.',
    'IN_PROGRESS': 'Issue is being processed.',
    'DONE': 'Issue has been resolved.',
}


class IssueViewSet(viewsets.ModelViewSet):

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