from math import asin, cos, radians, sin, sqrt
from rest_framework import serializers


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
    latitude_delta = radius_meters / 111_320

    longitude_scale = (
        111_320 * abs(cos(radians(gps_lat)))
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