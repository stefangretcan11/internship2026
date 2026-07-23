from math import asin, cos, radians, sin, sqrt
from rest_framework import serializers
from django.db.models import Count, Q
from issue.models import Issue
from users.models import CustomUser


def add_citizen_recipients(alert):
    from issue.models import AlertRecipient
    issue = alert.issue

    recipient_ids = {issue.owner_id}

    follower_ids = issue.followers.values_list(
        "user_id",
        flat=True,
    )

    recipient_ids.update(follower_ids)

    AlertRecipient.objects.bulk_create(
        [
            AlertRecipient(
                alert=alert,
                user_id=user_id,
            )
            for user_id in recipient_ids
        ],
        ignore_conflicts=True,
    )


def validate_latitude(value):
    if not -90 <= value <= 90:
        raise serializers.ValidationError(
            "Latitude must be between -90 and 90."
        )

    return value


def validate_longitude(value):
    if not -180 <= value <= 180:
        raise serializers.ValidationError(
            "Longitude must be between -180 and 180."
        )

    return value


EARTH_RADIUS_METERS = 6_371_000
METERS_PER_LATITUDE_DEGREE = 111_320

MAX_ACTIVE_ISSUES_FOR_AVAILABLE = 3

ACTIVE_AGENT_ISSUE_STATUSES = (
    Issue.Status.NEW,
    Issue.Status.DELAYED,
    Issue.Status.IN_PROGRESS,
)


def calculate_distance_meters(
        lat1,
        long1,
        lat2,
        long2,
):
    lat1 = radians(lat1)
    long1 = radians(long1)
    lat2 = radians(lat2)
    long2 = radians(long2)

    delta_lat = lat2 - lat1
    delta_long = long2 - long1

    haversine_value = (
            sin(delta_lat / 2) ** 2
            + cos(lat1)
            * cos(lat2)
            * sin(delta_long / 2) ** 2
    )

    central_angle = 2 * asin(sqrt(haversine_value))

    return EARTH_RADIUS_METERS * central_angle


def calculate_bounding_box(
        gps_lat,
        gps_long,
        radius_meters,
):
    latitude_delta = radius_meters / METERS_PER_LATITUDE_DEGREE

    longitude_scale = (
            METERS_PER_LATITUDE_DEGREE * abs(cos(radians(gps_lat)))
    )

    if longitude_scale == 0:
        longitude_delta = 180
    else:
        longitude_delta = (
                radius_meters / longitude_scale
        )

    min_latitude = max(
        -90,
        gps_lat - latitude_delta,
    )
    max_latitude = min(
        90,
        gps_lat + latitude_delta,
    )

    min_longitude = max(
        -180,
        gps_long - longitude_delta,
    )
    max_longitude = min(
        180,
        gps_long + longitude_delta,
    )

    return {
        "min_latitude": min_latitude,
        "max_latitude": max_latitude,
        "min_longitude": min_longitude,
        "max_longitude": max_longitude,
    }


def calculate_agents_availability():
    agents = (
        CustomUser.objects.filter(
            role=CustomUser.Role.AGENT,
            status=CustomUser.Status.ACTIVE,
        )
        .annotate(
            active_issues_count=Count(
                "assigned_issues",
                filter=Q(
                    assigned_issues__status__in=(
                        ACTIVE_AGENT_ISSUE_STATUSES
                    ),
                    assigned_issues__validation_status=(
                        Issue.ValidationStatus.VALIDATED
                    ),
                ),
                distinct=True,
            )
        )
    )

    total_agents = agents.count()

    available_agents = agents.filter(
        active_issues_count__lte=(
            MAX_ACTIVE_ISSUES_FOR_AVAILABLE
        )
    ).count()

    busy_agents = total_agents - available_agents

    if total_agents == 0:
        availability_percentage = 0
    else:
        availability_percentage = round(
            available_agents / total_agents * 100
        )

    return {
        "total_agents": total_agents,
        "available_agents": available_agents,
        "busy_agents": busy_agents,
        "availability_percentage": (
            availability_percentage
        ),
        "capacity_threshold": (
            MAX_ACTIVE_ISSUES_FOR_AVAILABLE
        ),
    }


def try_auto_assign(issue):
    # case 1 no zone was set on the issue at all
    if issue.zone is None:
        return {"status": "no_zone_match", "assigned_agent": None, "available_agents": []}

    # skip if already assigned
    if issue.assigned is not None:
        return {"status": "assigned", "assigned_agent": issue.assigned, "available_agents": []}

    def annotate_agents(queryset):
            # annotata  any agent queryset with their activate count 
        return queryset.filter(
            status=CustomUser.Status.ACTIVE
        ).annotate(
            active_issues_count=Count(
                "assigned_issues",
                filter=Q(
                    assigned_issues__status__in=ACTIVE_AGENT_ISSUE_STATUSES,
                    assigned_issues__validation_status=Issue.ValidationStatus.VALIDATED,
                ),
                distinct=True,
            )
        )

    # case 2: try to find an available agent in the issue's own zone
    zone_agents = annotate_agents(issue.zone.agents.all())
    available_in_zone = zone_agents.filter(
        active_issues_count__lt=MAX_ACTIVE_ISSUES_FOR_AVAILABLE
    ).order_by("active_issues_count")

    best_agent = available_in_zone.first()
    if best_agent:
        issue.assigned = best_agent
        issue.save(update_fields=["assigned", "date_updated"])
        return {"status": "assigned", "assigned_agent": best_agent, "available_agents": []}

    # case 3: zone is overloaded look in other zones for available agents
    neighboring_agents = annotate_agents(
        CustomUser.objects.filter(
            role=CustomUser.Role.AGENT,
            zones__isnull=False
        ).exclude(zones=issue.zone)
    ).filter(
        active_issues_count__lt=MAX_ACTIVE_ISSUES_FOR_AVAILABLE
    ).select_related().prefetch_related("zones")

    available_neighbors = list(neighboring_agents)

    if available_neighbors:
        # zone is overloaded so get the neighbours
        return {"status": "zone_overloaded", "assigned_agent": None, "available_agents": available_neighbors}

    # case 4: Everything is at capacity
    return {"status": "all_zones_overloaded", "assigned_agent": None, "available_agents": []}

