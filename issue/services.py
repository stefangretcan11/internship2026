from math import asin, cos, radians, sin, sqrt


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