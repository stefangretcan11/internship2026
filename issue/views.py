from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, F

from issue.models import Comment, Issue, IssueReport
from issue.serializers import CommentSerializer
from .services import calculate_distance_meters

from users.models import CustomUser
from users.permissions import (
    CanCreateIssue,
    IsAdmin,
    IsAdminOrValidator,
    IsIssueOwner,
    IsIssueOwnerOrAdmin,
    IsCommentOwner
)

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

        if user.role in {
            CustomUser.Role.ADMIN,
            CustomUser.Role.SUPERADMIN,
            CustomUser.Role.VALIDATOR,
            CustomUser.Role.AGENT,
        }:
            return queryset

        return queryset.filter(
            Q(owner=user)
            | Q(validation_status=Issue.ValidationStatus.VALIDATED)
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
        if self.action in {"validated", "rejected", "incomplete"}:
            return [
                IsAuthenticated(),
                IsAdminOrValidator(),
            ]

        if self.action == "pending":
            return [
                IsAuthenticated(),
                IsIssueOwner(),
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
            validation_status=Issue.ValidationStatus.PENDING,
            validation_message="",
        )

    def perform_update(self, serializer):
        # only agent/admin can change status
        if 'status' in self.request.data:
            if self.request.user.role not in {'agent', 'admin', 'superadmin'}:
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

    # Note: Preserved from HEAD branch. You might want to remove this
    # if `report_issue` replaces its functionality.
    def report(self, request, pk=None):
        issue = self.get_object()
        Issue.objects.filter(pk=issue.pk).update(report_count=F('report_count') + 1)
        issue.refresh_from_db(fields=['report_count'])
        return Response(
            {'report_count': issue.report_count},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path="validated",
    )
    def validated(self, request, pk=None):
        issue = self.get_object()

        issue.validation_status = Issue.ValidationStatus.VALIDATED
        issue.validation_message = ""
        issue.is_validated = True
        issue.is_private = False
        issue.validator = request.user

        issue.save(
            update_fields=[
                "validation_status",
                "validation_message",
                "is_validated",
                "is_private",
                "validator",
                "date_updated",
                "attachments"
            ]
        )

        serializer = IssueSerializer(
            issue,
            context=self.get_serializer_context(),
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path="rejected",
    )
    def rejected(self, request, pk=None):
        issue = self.get_object()

        message = request.data.get("message", "").strip()

        if not message:
            return Response(
                {
                    "message": "A rejection reason is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue.validation_status = (
            Issue.ValidationStatus.REJECTED_DUPLICATE
        )
        issue.validation_message = message
        issue.is_validated = False
        issue.validator = request.user

        issue.save(
            update_fields=[
                "validation_status",
                "validation_message",
                "is_validated",
                "validator",
                "date_updated",
                "attachments"
            ]
        )

        serializer = IssueSerializer(
            issue,
            context=self.get_serializer_context(),
        )

        return Response(serializer.data)

    @action(
        detail=True,
        methods=["patch"],
        url_path="incomplete",
    )
    def incomplete(self, request, pk=None):
        issue = self.get_object()

        message = request.data.get("message", "").strip()

        if not message:
            return Response(
                {
                    "message": (
                        "A message describing the required changes is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue.validation_status = (
            Issue.ValidationStatus.CHANGES_REQUESTED
        )
        issue.validation_message = message
        issue.is_validated = False
        issue.validator = request.user

        issue.save(
            update_fields=[
                "validation_status",
                "validation_message",
                "is_validated",
                "validator",
                "date_updated",
                "attachments"
            ]
        )

        serializer = IssueSerializer(
            issue,
            context=self.get_serializer_context(),
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path="pending",
    )
    def pending(self, request, pk=None):
        issue = self.get_object()

        if (
                issue.validation_status
                != Issue.ValidationStatus.CHANGES_REQUESTED
        ):
            return Response(
                {
                    "message": (
                        "Only incomplete issues can be resubmitted."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue.validation_status = Issue.ValidationStatus.PENDING
        issue.validation_message = ""
        issue.is_validated = False
        issue.validator = None

        issue.save(
            update_fields=[
                "validation_status",
                "validation_message",
                "is_validated",
                "validator",
                "date_updated",
                "attachments"
            ]
        )

        serializer = IssueSerializer(
            issue,
            context=self.get_serializer_context(),
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="nearby",
    )
    def nearby(self, request):
        gps_lat = request.query_params.get("gps_lat")
        gps_long = request.query_params.get("gps_long")
        radius = request.query_params.get("radius", 500)

        if gps_lat is None or gps_long is None:
            return Response(
                {
                    "message": (
                        "gps_lat and gps_long are required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            gps_lat = float(gps_lat)
            gps_long = float(gps_long)
            radius = float(radius)
        except (TypeError, ValueError):
            return Response(
                {
                    "message": (
                        "gps_lat, gps_long and radius "
                        "must be valid numbers."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not -90 <= gps_lat <= 90:
            return Response(
                {
                    "message": (
                        "gps_lat must be between -90 and 90."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not -180 <= gps_long <= 180:
            return Response(
                {
                    "message": (
                        "gps_long must be between -180 and 180."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if radius <= 0:
            return Response(
                {
                    "message": (
                        "radius must be greater than 0."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        open_issues = Issue.objects.exclude(
            status=Issue.Status.DONE
        ).filter(
            validation_status=Issue.ValidationStatus.VALIDATED
        )

        nearby_issues = []

        for issue in open_issues:
            distance = calculate_distance_meters(
                gps_lat,
                gps_long,
                issue.gps_lat,
                issue.gps_long,
            )

            if distance <= radius:
                nearby_issues.append({
                    "issue": issue,
                    "distance_meters": round(distance, 2),
                })

        nearby_issues.sort(
            key=lambda item: item["distance_meters"]
        )

        response_data = []

        for item in nearby_issues:
            serialized_issue = IssueSerializer(
                item["issue"],
                context=self.get_serializer_context(),
            ).data

            serialized_issue["distance_meters"] = (
                item["distance_meters"]
            )

            response_data.append(serialized_issue)

        return Response(
            response_data,
            status=status.HTTP_200_OK,
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
            return [IsAuthenticated(), IsCommentOwner(), IsAdmin()]
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