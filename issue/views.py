import json
from datetime import timezone
import time
from django.http import StreamingHttpResponse
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from django.db.models import Q, F
from django_filters.rest_framework import DjangoFilterBackend
from issue.models import Comment, Issue, IssueReport, Alert
from django.core.cache import cache
from rest_framework.exceptions import Throttled
from issue.serializers import (
    CommentSerializer,
    IssueAssignSerializer,
    IssueSerializer,
    IssueUpdateSerializer,
    AlertSerializer
)
from issue.utils import (
    calculate_bounding_box,
    calculate_distance_meters,
)

from users.models import CustomUser
from users.permissions import (
    CanCreateIssue,
    IsAdmin,
    IsAdminOrValidator,
    IsCommentOwner,
    IsIssueOwner,
    IsIssueOwnerOrAdmin, IsActiveOrReadOnly,
)
from users.throttles import IssueCreationThrottle

STATUS_MESSAGES = {
    Issue.Status.NEW: "Issue has been created.",
    Issue.Status.DELAYED: "Issue has been delayed.",
    Issue.Status.IN_PROGRESS: "Issue is being processed.",
    Issue.Status.DONE: "Issue has been resolved.",
}


class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    permission_classes = [IsAuthenticated, IsActiveOrReadOnly]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status']
    search_fields = ['title', 'description']

    def get_queryset(self):
        user = self.request.user

        queryset = (
            Issue.objects.select_related(
                "owner",
                "assigned",
                "validator",
            )
            .prefetch_related("attachments")
            .order_by("-report_count", "-date_created")
        )

        if user.role in {
            CustomUser.Role.ADMIN,
            CustomUser.Role.SUPERADMIN,
            CustomUser.Role.VALIDATOR,
        }:
            return queryset

        if user.role == CustomUser.Role.AGENT:
            return queryset.filter(assigned=user)

        return queryset.filter(
            (
                    Q(owner=user)
                    & ~Q(
                validation_status=(
                    Issue.ValidationStatus.REJECTED_DUPLICATE
                )
            )
            )
            | Q(
                validation_status=(
                    Issue.ValidationStatus.VALIDATED
                )
            )
        ).distinct()

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return IssueUpdateSerializer

        if self.action == "assign":
            return IssueAssignSerializer

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

        if self.action in {
            "validated",
            "rejected",
            "incomplete",
            "assign",
        }:
            return [
                IsAuthenticated(),
                IsAdminOrValidator(),
            ]

        if self.action == "pending":
            return [
                IsAuthenticated(),
                IsIssueOwner(),
            ]

        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(
            owner=self.request.user,
            status=Issue.Status.NEW,
            is_validated=False,
            validation_status=Issue.ValidationStatus.PENDING,
            validation_message="",
        )

    def perform_update(self, serializer):
        if "status" in self.request.data:
            allowed_roles = {
                CustomUser.Role.AGENT,
                CustomUser.Role.ADMIN,
                CustomUser.Role.SUPERADMIN,
            }

            if self.request.user.role not in allowed_roles:
                raise PermissionDenied(
                    "Only agents or admins can change issue status."
                )

        issue = self.get_object()
        old_status = issue.status

        updated_issue = serializer.save()
        new_status = updated_issue.status

        if old_status != new_status:
            message = STATUS_MESSAGES.get(
                new_status,
                f"Status changed to {new_status}.",
            )

            Comment.objects.create(
                issue=updated_issue,
                user=self.request.user,
                description=(
                    f"Status changed from {old_status} "
                    f"to {new_status}. {message}"
                ),
                is_system=True,
            )

    @action(
        detail=True,
        methods=["post"],
        url_path="report",
    )
    def report_issue(self, request, pk=None):
        issue = self.get_object()

        report, created = IssueReport.objects.get_or_create(
            issue=issue,
            user=request.user,
        )

        if not created:
            return Response(
                {
                    "detail": (
                        "You have already reported this issue."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        issue.report_count = F('report_count') + 1
        issue.save(update_fields=["report_count"])
        issue.refresh_from_db(fields=["report_count"])

        return Response(
            {
                "detail": "Issue reported.",
                "report_count": issue.report_count,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["put"],
        url_path="validated",
    )
    def validated(self, request, pk=None):
        issue = self.get_object()

        issue.validation_status = (
            Issue.ValidationStatus.VALIDATED
        )
        issue.validation_message = ""
        issue.is_validated = True
        issue.validator = request.user

        issue.save(
            update_fields=[
                "validation_status",
                "validation_message",
                "is_validated",
                "validator",
                "date_updated",
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
        methods=["put"],
        url_path="rejected",
    )
    def rejected(self, request, pk=None):
        issue = self.get_object()

        message = request.data.get("message", "").strip()

        if not message:
            return Response(
                {
                    "message": (
                        "A rejection reason is required."
                    )
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
        methods=["put"],
        url_path="incomplete",
    )
    def incomplete(self, request, pk=None):
        issue = self.get_object()

        message = request.data.get("message", "").strip()

        if not message:
            return Response(
                {
                    "message": (
                        "A message describing the required "
                        "changes is required."
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
        methods=["put"],
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
    def nearby_validated_issues(self, request):
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

        bounding_box = calculate_bounding_box(
            gps_lat=gps_lat,
            gps_long=gps_long,
            radius_meters=radius,
        )
        open_issues = (
            Issue.objects.filter(
                validation_status=(
                    Issue.ValidationStatus.VALIDATED
                ),
                gps_lat__range=(
                    bounding_box["min_latitude"],
                    bounding_box["max_latitude"],
                ),
                gps_long__range=(
                    bounding_box["min_longitude"],
                    bounding_box["max_longitude"],
                ),
            )
            .exclude(
                status=Issue.Status.DONE,
            )
            .select_related(
                "owner",
                "assigned",
                "validator",
            )
            .prefetch_related("attachments")
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
                nearby_issues.append(
                    {
                        "issue": issue,
                        "distance_meters": round(distance, 2),
                    }
                )

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

    @action(
        detail=True,
        methods=["patch"],
        url_path="assign",
    )
    def assign(self, request, pk=None):
        issue = self.get_object()

        serializer = self.get_serializer(
            issue,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        updated_issue = serializer.save()

        response_serializer = IssueSerializer(
            updated_issue,
            context=self.get_serializer_context(),
        )

        return Response(
            {
                "message": "Issue assigned successfully.",
                "issue": response_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def get_throttles(self):
        if self.action == 'create':
            return [IssueCreationThrottle()]
        return super().get_throttles()

class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        issue_pk = self.kwargs.get("issue_pk")

        queryset = Comment.objects.filter(issue_id=issue_pk).order_by("-date_created")

        if user.role in {
            CustomUser.Role.ADMIN,
            CustomUser.Role.SUPERADMIN,
            CustomUser.Role.VALIDATOR,
            CustomUser.Role.AGENT
        }:
            return queryset

        # citizens can see their own issues or the validates ones
        return queryset.filter(
            (
                    Q(issue__owner=user)
                    & ~Q(issue__validation_status=Issue.ValidationStatus.REJECTED_DUPLICATE)
            )
            | Q(issue__validation_status=Issue.ValidationStatus.VALIDATED)
        ).distinct()

    def perform_create(self, serializer):
        issue_pk = self.kwargs["issue_pk"]

        if not Issue.objects.filter(id=issue_pk).exists():
            raise NotFound("Issue not found.")

        serializer.save(
            user=self.request.user,
            issue_id=issue_pk,
        )

    def perform_update(self, serializer):
        comment = self.get_object()

        if comment.is_system:
            raise PermissionDenied(
                "System comments cannot be modified."
            )

        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_system:
            raise PermissionDenied("System comments cannot be deleted.")
        instance.delete()


class AlertViewSet(viewsets.ModelViewSet):
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Alert.objects.all().order_by('-date_created')

        if user.role == CustomUser.Role.CITIZEN:
            return queryset.filter(
                Q(issue__owner=user) &
                (Q(name__startswith='STATUS CHANGE') | Q(name__startswith='AGENT ASSIGNED'))
            )
        else:
            return queryset.filter(Q(name__startswith='NEW ISSUE') | Q(name__startswith='ESCALATION'))

    def perform_create(self, serializer):

        serializer.save(status=Alert.Status.NEW)

    @extend_schema(request=None)
    # correct the auto-generated documentation
    @action(
        detail=True,
        methods=["put"],
        url_path="seen",
    )
    def mark_seen(self, request, pk=None):
        alert = self.get_object()

        if alert.status == Alert.Status.NEW:
            alert.status = Alert.Status.SEEN
            alert.save(update_fields=['status'])

        serializer = self.get_serializer(alert)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: str})
    @action(detail=False, methods=["get"], url_path="stream")
    def stream(self, request):
        def event_stream():
            user = request.user
            last_checked = timezone.now()

            while True:
                new_alerts = Alert.objects.filter(
                    status=Alert.Status.NEW,
                    date_created__gt=last_checked
                ).order_by('date_created')

                # query for new alerts created recently
                new_alerts = Alert.objects.filter(
                    status=Alert.Status.NEW,
                    date_created__gt=last_checked
                ).order_by('date_created')
                if user.role == CustomUser.Role.CITIZEN:
                    new_alerts = new_alerts.filter(
                        Q(issue__owner=user) &
                        (Q(name__startswith='STATUS CHANGE') | Q(name__startswith='AGENT ASSIGNED'))
                    )
                else:
                    new_alerts = new_alerts.filter(Q(name__startswith='NEW ISSUE') | Q(name__startswith='ESCALATION'))
                for alert in new_alerts:
                    # payload as json
                    data = json.dumps({
                        "id": str(alert.id),
                        "name": alert.name,
                        "issue_id": str(alert.issue_id),
                        "date_created": alert.date_created.isoformat()
                    })
                    # SSE standard requires data: <content>\n\n
                    yield f"data: {data}\n\n"

                last_checked = timezone.now()
                # wait 30 seconds before checking the database again
                time.sleep(30)

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        # prevent browsers and proxies from caching the stream
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    @action(detail=False, methods=["get"], url_path="unseen_count")
    def unseen_count(self, request):

        queryset = self.get_queryset()
        count = queryset.filter(status=Alert.Status.NEW).count()
        return Response({"unseen_count": count}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["put"], url_path="mark_all_seen")
    def mark_all_seen(self, request):

        queryset = self.get_queryset()
        updated_count = queryset.filter(status=Alert.Status.NEW).update(status=Alert.Status.SEEN)
        return Response(
            {
                "message": "All alerts marked as seen.",
                "updated_count": updated_count
            },
            status=status.HTTP_200_OK
        )

