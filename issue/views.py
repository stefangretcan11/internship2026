import json
from django.db.models import Q, F, Count
from django.db.models.functions import TruncMonth
from django.http import StreamingHttpResponse, HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from issue.models import (
    Alert,
    Comment,
    Issue,
    IssueFollower,
    IssueReport,
)
from issue.serializers import (
    AlertSerializer,
    CommentSerializer,
    IssueAssignSerializer,
    IssueSerializer,
    IssueUpdateSerializer,
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
    IsIssueOwnerOrAdmin,
    IsActiveOrReadOnly,
)
from users.throttles import IssueCreationThrottle
from zone.models import Zone

STATUS_MESSAGES = {
    Issue.Status.NEW: "Issue has been created.",
    Issue.Status.DELAYED: "Issue has been delayed.",
    Issue.Status.IN_PROGRESS: "Issue is being processed.",
    Issue.Status.DONE: "Issue has been resolved.",
}

STREAM_POLL_SECONDS = 5

STAFF_ROLES = {
    CustomUser.Role.ADMIN,
    CustomUser.Role.SUPERADMIN,
    CustomUser.Role.VALIDATOR,
}


def can_view_issue(user, issue):
    if user.role in STAFF_ROLES or user.role == CustomUser.Role.AGENT:
        return True

    if issue.owner_id == user.id:
        return issue.validation_status != Issue.ValidationStatus.REJECTED_DUPLICATE

    return issue.validation_status == Issue.ValidationStatus.VALIDATED


def get_alert_queryset_for_user(user, base_qs=None):
    """Return the correctly-scoped alert queryset for *user*.

    Extracted so it can be reused in both the REST ViewSet and the async
    SSE view without duplicating the filter logic.
    """
    qs = (base_qs if base_qs is not None else Alert.objects.all())

    if user.role == CustomUser.Role.CITIZEN:
        return qs.filter(
            Q(issue__owner=user)
            & (
                Q(name__startswith="STATUS CHANGE")
                | Q(name__startswith="AGENT ASSIGNED")
            )
        )
    return qs.filter(
        Q(name__startswith="NEW ISSUE") | Q(name__startswith="ESCALATION")
    )

class IssueViewSet(viewsets.ModelViewSet):
    queryset = Issue.objects.all()
    serializer_class = IssueSerializer
    permission_classes = [IsAuthenticated, IsActiveOrReadOnly]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "status"]
    search_fields = ["title", "description"]

    def get_queryset(self):
        return (
            Issue.objects.select_related("owner", "assigned", "validator")
            .prefetch_related("attachments")
            .order_by("-report_count", "-date_created")
        )

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return IssueUpdateSerializer
        if self.action == "assign":
            return IssueAssignSerializer
        return IssueSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), CanCreateIssue()]

        if self.action in {"update", "partial_update"}:
            return [IsAuthenticated(), IsIssueOwnerOrAdmin()]

        if self.action == "destroy":
            return [IsAuthenticated(), IsAdmin()]

        if self.action in {"validated", "rejected", "incomplete", "assign"}:
            return [IsAuthenticated(), IsAdminOrValidator()]

        if self.action == "pending":
            return [IsAuthenticated(), IsIssueOwner()]

        return [IsAuthenticated()]

    def get_throttles(self):
        if self.action == "create":
            return [IssueCreationThrottle()]
        return super().get_throttles()

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
                raise PermissionDenied("Only agents or admins can change issue status.")

        old_status = serializer.instance.status
        updated_issue = serializer.save()
        new_status = updated_issue.status

        if old_status != new_status:
            message = STATUS_MESSAGES.get(new_status, f"Status changed to {new_status}.")
            Comment.objects.create(
                issue=updated_issue,
                user=self.request.user,
                description=f"Status changed from {old_status} to {new_status}. {message}",
                is_system=True,
            )
            Alert.objects.create(
                issue=updated_issue,
                name=f"STATUS CHANGE: {old_status} → {new_status}",
                status=Alert.Status.NEW,
            )

    @action(detail=False, methods=["get"], url_path="user")
    def my_issues(self, request):
        queryset = (
            Issue.objects.filter(owner=request.user)
            .select_related("owner", "assigned", "validator")
            .prefetch_related("attachments")
            .order_by("-report_count", "-date_created")
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="report")
    def report_issue(self, request, pk=None):
        issue = self.get_object()
        _, created = IssueReport.objects.get_or_create(issue=issue, user=request.user)

        if not created:
            return Response(
                {"detail": "You have already reported this issue."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue.report_count = F("report_count") + 1
        issue.save(update_fields=["report_count"])
        issue.refresh_from_db(fields=["report_count"])

        return Response(
            {"detail": "Issue reported.", "report_count": issue.report_count},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post", "delete"], url_path="follow")
    def follow(self, request, pk=None):
        issue = self.get_object()
        user = request.user

        if user.role != CustomUser.Role.CITIZEN:
            return Response(
                {"message": "Only citizens can follow issues."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if issue.owner_id == user.id:
            return Response(
                {"message": "You already receive notifications for your own issue."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if issue.validation_status != Issue.ValidationStatus.VALIDATED:
            return Response(
                {"message": "Only validated issues can be followed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.method == "POST":
            _, created = IssueFollower.objects.get_or_create(issue=issue, user=user)

            if not created:
                return Response(
                    {"message": "You are already following this issue."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "message": "Issue followed successfully.",
                    "is_following": True,
                    "followers_count": issue.followers.count(),
                },
                status=status.HTTP_201_CREATED,
            )

        deleted_count, _ = IssueFollower.objects.filter(issue=issue, user=user).delete()

        if deleted_count == 0:
            return Response(
                {"message": "You are not following this issue."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Issue unfollowed successfully.",
                "is_following": False,
                "followers_count": issue.followers.count(),
            },
            status=status.HTTP_200_OK,
        )


    def _set_validation(self, request, *, validation_status, is_validated, message=""):
        """Apply a validation state transition and return the serialized issue."""
        issue = self.get_object()

        issue.validation_status = validation_status
        issue.validation_message = message
        issue.is_validated = is_validated
        issue.validator = (
            request.user if validation_status != Issue.ValidationStatus.PENDING else None
        )

        issue.save(
            update_fields=[
                "validation_status",
                "validation_message",
                "is_validated",
                "validator",
                "date_updated",
            ]
        )

        serializer = IssueSerializer(issue, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["put"], url_path="validated")
    def validated(self, request, pk=None):
        return self._set_validation(
            request,
            validation_status=Issue.ValidationStatus.VALIDATED,
            is_validated=True,
        )

    @action(detail=True, methods=["put"], url_path="rejected")
    def rejected(self, request, pk=None):
        message = request.data.get("message", "").strip()
        if not message:
            return Response(
                {"message": "A rejection reason is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self._set_validation(
            request,
            validation_status=Issue.ValidationStatus.REJECTED_DUPLICATE,
            is_validated=False,
            message=message,
        )

    @action(detail=True, methods=["put"], url_path="incomplete")
    def incomplete(self, request, pk=None):
        message = request.data.get("message", "").strip()
        if not message:
            return Response(
                {"message": "A message describing the required changes is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self._set_validation(
            request,
            validation_status=Issue.ValidationStatus.CHANGES_REQUESTED,
            is_validated=False,
            message=message,
        )

    @action(detail=True, methods=["put"], url_path="pending")
    def pending(self, request, pk=None):
        issue = self.get_object()

        if issue.validation_status != Issue.ValidationStatus.CHANGES_REQUESTED:
            return Response(
                {"message": "Only incomplete issues can be resubmitted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return self._set_validation(
            request,
            validation_status=Issue.ValidationStatus.PENDING,
            is_validated=False,
        )

    @action(detail=False, methods=["get"], url_path="nearby")
    def nearby_validated_issues(self, request):
        gps_lat = request.query_params.get("gps_lat")
        gps_long = request.query_params.get("gps_long")
        radius = request.query_params.get("radius", 500)

        if gps_lat is None or gps_long is None:
            return Response(
                {"message": "gps_lat and gps_long are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            gps_lat = float(gps_lat)
            gps_long = float(gps_long)
            radius = float(radius)
        except (TypeError, ValueError):
            return Response(
                {"message": "gps_lat, gps_long and radius must be valid numbers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not -90 <= gps_lat <= 90:
            return Response(
                {"message": "gps_lat must be between -90 and 90."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not -180 <= gps_long <= 180:
            return Response(
                {"message": "gps_long must be between -180 and 180."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if radius <= 0:
            return Response(
                {"message": "radius must be greater than 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bounding_box = calculate_bounding_box(
            gps_lat=gps_lat,
            gps_long=gps_long,
            radius_meters=radius,
        )
        open_issues = (
            Issue.objects.filter(
                validation_status=Issue.ValidationStatus.VALIDATED,
                gps_lat__range=(bounding_box["min_latitude"], bounding_box["max_latitude"]),
                gps_long__range=(bounding_box["min_longitude"], bounding_box["max_longitude"]),
            )
            .exclude(status=Issue.Status.DONE)
            .select_related("owner", "assigned", "validator")
            .prefetch_related("attachments")
        )

        nearby_issues = sorted(
            (
                {"issue": issue, "distance_meters": round(distance, 2)}
                for issue in open_issues
                if (
                    distance := calculate_distance_meters(
                        gps_lat, gps_long, issue.gps_lat, issue.gps_long
                    )
                )
                <= radius
            ),
            key=lambda item: item["distance_meters"],
        )

        response_data = []
        for item in nearby_issues:
            serialized = IssueSerializer(
                item["issue"], context=self.get_serializer_context()
            ).data
            serialized["distance_meters"] = item["distance_meters"]
            response_data.append(serialized)

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="assign")
    def assign(self, request, pk=None):
        issue = self.get_object()

        # partial=True only `agent_id` is expected in the payload
        serializer = self.get_serializer(issue, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_issue = serializer.save()

        # Notify the issue owner that an agent has been assigned.
        Alert.objects.create(
            issue=updated_issue,
            name=f"AGENT ASSIGNED: {updated_issue.assigned.get_full_name() or updated_issue.assigned.email}",
            status=Alert.Status.NEW,
        )

        response_serializer = IssueSerializer(
            updated_issue, context=self.get_serializer_context()
        )
        return Response(
            {"message": "Issue assigned successfully.", "issue": response_serializer.data},
            status=status.HTTP_200_OK,
        )


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # own it reading or creating only needs auth.
        if self.action in {"update", "partial_update", "destroy"}:
            return [IsAuthenticated(), IsCommentOwner()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        issue_pk = self.kwargs.get("issue_pk")

        queryset = Comment.objects.filter(issue_id=issue_pk).order_by("-date_created")

        if user.role in STAFF_ROLES or user.role == CustomUser.Role.AGENT:
            return queryset

        # Citizens see comments on their own non-rejected issues or validated ones.
        return queryset.filter(
            (
                Q(issue__owner=user)
                & ~Q(issue__validation_status=Issue.ValidationStatus.REJECTED_DUPLICATE)
            )
            | Q(issue__validation_status=Issue.ValidationStatus.VALIDATED)
        ).distinct()

    def perform_create(self, serializer):
        issue_pk = self.kwargs["issue_pk"]
        issue = get_object_or_404(Issue, id=issue_pk)
        user = self.request.user

        # Write access mirrors read access — prevents commenting on invisible issues.
        if not can_view_issue(user, issue):
            raise PermissionDenied("You cannot comment on this issue.")

        serializer.save(user=user, issue_id=issue_pk)

    def perform_update(self, serializer):
        if serializer.instance.is_system:
            raise PermissionDenied("System comments cannot be modified.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.is_system:
            raise PermissionDenied("System comments cannot be deleted.")
        instance.delete()



import time

class AlertViewSet(viewsets.ModelViewSet):
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_alert_queryset_for_user(
            self.request.user,
            base_qs=Alert.objects.all().order_by("-date_created"),
        )

    def perform_create(self, serializer):
        serializer.save(status=Alert.Status.NEW)

    @extend_schema(request=None)
    @action(detail=True, methods=["put"], url_path="seen")
    def mark_seen(self, request, pk=None):
        alert = self.get_object()
        if alert.status == Alert.Status.NEW:
            alert.status = Alert.Status.SEEN
            alert.save(update_fields=["status"])
        return Response(self.get_serializer(alert).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="unseen_count")
    def unseen_count(self, request):
        count = self.get_queryset().filter(status=Alert.Status.NEW).count()
        return Response({"unseen_count": count}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["put"], url_path="mark_all_seen")
    def mark_all_seen(self, request):
        updated_count = (
            self.get_queryset()
            .filter(status=Alert.Status.NEW)
            .update(status=Alert.Status.SEEN)
        )
        return Response(
            {"message": "All alerts marked as seen.", "updated_count": updated_count},
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        responses={200: str},
    )
    @action(detail=False, methods=["get"], url_path="stream")
    def stream(self, request):
        user = request.user

        def event_stream():
            last_checked = timezone.now()
            yield "retry: 5000\n\n"

            while True:
                new_alerts = list(
                    get_alert_queryset_for_user(
                        user,
                        base_qs=Alert.objects.filter(
                            status=Alert.Status.NEW,
                            date_created__gt=last_checked,
                        ).order_by("date_created"),
                    )
                )

                for alert in new_alerts:
                    payload = json.dumps({
                        "id": str(alert.id),
                        "name": alert.name,
                        "issue_id": str(alert.issue_id),
                        "date_created": alert.date_created.isoformat(),
                    })
                    yield f"data: {payload}\n\n"

                last_checked = timezone.now()
                time.sleep(STREAM_POLL_SECONDS)

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response


class IssueStatisticsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrValidator]

    def get(self, request):
        # Consistent param names: date_from / date_to
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        zone_id = request.query_params.get("zone_id")

        queryset = Issue.objects.all()

        if date_from:
            queryset = queryset.filter(date_created__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date_created__date__lte=date_to)

        # Issues are linked to zones via the assigned agent
        # (Zone ↔ agents M2M, agents ↔ assigned_issues reverse FK).
        if zone_id:
            queryset = queryset.filter(assigned__zones__id=zone_id)

        rows = (
            queryset
            .annotate(month=TruncMonth("date_created"))
            .values("month", "status")
            .annotate(count=Count("id"))
            .order_by("month", "status")
        )

        results = {}
        for row in rows:
            month_key = row["month"].strftime("%Y-%m")
            if month_key not in results:
                results[month_key] = {
                    "month": month_key,
                    "new": 0,
                    "delayed": 0,
                    "in_progress": 0,
                    "done": 0,
                }
            results[month_key][row["status"]] = row["count"]

        return Response(list(results.values()), status=status.HTTP_200_OK)


class ZoneStatisticsView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrValidator]

    def get(self, request):
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        issue_qs = Issue.objects.all()
        if date_from:
            issue_qs = issue_qs.filter(date_created__date__gte=date_from)
        if date_to:
            issue_qs = issue_qs.filter(date_created__date__lte=date_to)

        # Single annotated query instead of one COUNT per zone in a loop.
        # Annotates each Zone with the number of issues assigned to any of
        # its agents, respecting the optional date filter via a subquery filter.
        zones = (
            Zone.objects.annotate(
                issue_count=Count(
                    "agents__assigned_issues",
                    filter=Q(agents__assigned_issues__in=issue_qs),
                )
            )
            .order_by("issue_count")
        )

        results = []
        total = zones.count()

        for i, zone in enumerate(zones):
            tier = min(4, int(i / total * 4) + 1) if total else 1
            results.append({
                "zone_id": str(zone.id),
                "zone_name": zone.name,
                "issue_count": zone.issue_count,
                "tier": tier,
            })

        return Response(results, status=status.HTTP_200_OK)