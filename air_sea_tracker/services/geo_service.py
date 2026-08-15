"""Observer-relative geographic calculations (SDR §18)."""

from __future__ import annotations

from utils.distance import bearing_deg, haversine_km, slant_distance_km


def distance_and_bearing(
    observer_lat: float, observer_lon: float, target_lat: float, target_lon: float
) -> tuple[float, float]:
    """Returns (great_circle_km, bearing_deg) from observer to target."""
    return (
        haversine_km(observer_lat, observer_lon, target_lat, target_lon),
        bearing_deg(observer_lat, observer_lon, target_lat, target_lon),
    )


def aircraft_slant_range_km(horizontal_km: float, altitude_m: float | None) -> float:
    if not altitude_m:
        return horizontal_km
    return slant_distance_km(horizontal_km, altitude_m)


def is_within_radius(
    observer_lat: float, observer_lon: float, target_lat: float, target_lon: float, radius_km: float
) -> bool:
    return haversine_km(observer_lat, observer_lon, target_lat, target_lon) <= radius_km


def bounding_box_km(center_lat: float, center_lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """Returns (lat_min, lon_min, lat_max, lon_max) covering a radius_km circle.

    Approximate (equirectangular), sufficient for subscribing collectors
    to a coverage area — actual radius filtering uses haversine (§18)
    via is_within_radius / distance_and_bearing.
    """
    import math

    lat_delta = radius_km / 111.32
    lon_delta = radius_km / (111.32 * max(0.01, math.cos(math.radians(center_lat))))

    lat_min = max(-90.0, center_lat - lat_delta)
    lat_max = min(90.0, center_lat + lat_delta)
    lon_min = max(-180.0, center_lon - lon_delta)
    lon_max = min(180.0, center_lon + lon_delta)
    return lat_min, lon_min, lat_max, lon_max
