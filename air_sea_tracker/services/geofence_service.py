"""Port/airport geofencing and traffic classification (SDR §10-11, Phase 3).

Vessel status is inferred purely from the latest position/course — there's
no stored "previous position at time of last classification" to diff
against, so "departing" vs "approaching" is read off course-over-ground
relative to the bearing to the port rather than off a state transition.
"""

from __future__ import annotations

from models.aircraft import Aircraft
from models.airport import Airport
from models.port import Port
from models.vessel import Vessel
from services.geo_service import distance_and_bearing

APPROACH_BAND_MULTIPLIER = 3.0  # geofence_radius_km * this = "approaching/departing" band
COURSE_ALIGNMENT_DEG = 45.0  # how close course-over-ground must track the port bearing
STATIONARY_KT = 0.5
AIRPORT_VICINITY_KM = 10.0
AIRPORT_APPROACH_BAND_KM = 50.0

STATUS_IN_PORT = "In port"
STATUS_ANCHORED = "Anchored"
STATUS_APPROACHING = "Approaching"
STATUS_DEPARTING = "Departing"
STATUS_PASSING = "Passing nearby"


def classify_vessel(port: Port, vessel: Vessel) -> str | None:
    """None means the vessel is outside any classification band for this port."""
    distance_km, bearing_to_port = distance_and_bearing(vessel.latitude, vessel.longitude, port.latitude, port.longitude)
    speed = vessel.speed_over_ground or 0.0

    if distance_km <= port.geofence_radius_km:
        if speed < STATIONARY_KT:
            return STATUS_ANCHORED if (vessel.navigation_status or "").lower().startswith("at anchor") else STATUS_IN_PORT
        return STATUS_IN_PORT

    band_km = port.geofence_radius_km * APPROACH_BAND_MULTIPLIER
    if distance_km <= band_km:
        course = vessel.effective_heading
        if course is None or speed < STATIONARY_KT:
            return STATUS_PASSING
        delta = abs(((course - bearing_to_port + 180) % 360) - 180)
        if delta <= COURSE_ALIGNMENT_DEG:
            return STATUS_APPROACHING
        if delta >= 180 - COURSE_ALIGNMENT_DEG:
            return STATUS_DEPARTING
        return STATUS_PASSING

    return None


def port_traffic(port: Port, vessels: list[Vessel]) -> dict[str, list[Vessel]]:
    groups: dict[str, list[Vessel]] = {
        STATUS_IN_PORT: [], STATUS_ANCHORED: [], STATUS_APPROACHING: [],
        STATUS_DEPARTING: [], STATUS_PASSING: [],
    }
    for vessel in vessels:
        status = classify_vessel(port, vessel)
        if status:
            groups[status].append(vessel)
    return groups


def inbound_radar(port: Port, vessels: list[Vessel], radius_km: float) -> list[tuple[Vessel, float]]:
    """Vessels within radius_km whose course is roughly aimed at the port,
    regardless of the port's own (much smaller) geofence — SDR §10."""
    results = []
    for vessel in vessels:
        distance_km, bearing_to_port = distance_and_bearing(
            vessel.latitude, vessel.longitude, port.latitude, port.longitude
        )
        if distance_km > radius_km:
            continue
        course = vessel.effective_heading
        if course is None or (vessel.speed_over_ground or 0) < STATIONARY_KT:
            continue
        delta = abs(((course - bearing_to_port + 180) % 360) - 180)
        if delta <= COURSE_ALIGNMENT_DEG:
            results.append((vessel, distance_km))
    results.sort(key=lambda t: t[1])
    return results


# --- airports (SDR §11) ---
# No free scheduled-flight-data source is wired up (Phase 5, §29), so this
# only ever classifies OBSERVED ADS-B traffic — the UI must label it as
# such rather than implying arrival/departure schedules are known.

STATUS_ON_GROUND = "On/near ground"
STATUS_AIRPORT_APPROACHING = "Approaching"
STATUS_AIRPORT_DEPARTING = "Departing"
STATUS_AIRPORT_NEARBY = "Nearby"


def classify_aircraft(airport: Airport, aircraft: Aircraft) -> str | None:
    distance_km, bearing_to_airport = distance_and_bearing(
        aircraft.latitude, aircraft.longitude, airport.latitude, airport.longitude
    )

    if distance_km <= AIRPORT_VICINITY_KM and (aircraft.on_ground or (aircraft.altitude_m or 0) < 500):
        return STATUS_ON_GROUND

    if distance_km <= AIRPORT_APPROACH_BAND_KM:
        course = aircraft.track
        if course is None:
            return STATUS_AIRPORT_NEARBY
        delta = abs(((course - bearing_to_airport + 180) % 360) - 180)
        if delta <= COURSE_ALIGNMENT_DEG and (aircraft.vertical_rate or 0) <= 0:
            return STATUS_AIRPORT_APPROACHING
        if delta >= 180 - COURSE_ALIGNMENT_DEG and (aircraft.vertical_rate or 0) >= 0:
            return STATUS_AIRPORT_DEPARTING
        return STATUS_AIRPORT_NEARBY

    return None


def airport_traffic(airport: Airport, aircraft_list: list[Aircraft]) -> dict[str, list[Aircraft]]:
    groups: dict[str, list[Aircraft]] = {
        STATUS_ON_GROUND: [], STATUS_AIRPORT_APPROACHING: [],
        STATUS_AIRPORT_DEPARTING: [], STATUS_AIRPORT_NEARBY: [],
    }
    for aircraft in aircraft_list:
        status = classify_aircraft(airport, aircraft)
        if status:
            groups[status].append(aircraft)
    return groups
