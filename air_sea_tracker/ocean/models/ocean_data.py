"""Unified ocean/environment data model (Ocean & Environment SDR §9).

Phase 2 extends the Phase 1 model with dynamic environmental fields
(§9's own note) rather than replacing it — the same OceanData instance
carries both, with Phase 2 fields left None when Phase 2 layers are
unavailable/disabled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Freshness/status vocabulary (SDR §19). Deliberately strings, not an
# enum: they're display labels first (badge text) and a status code
# second, and providers set them directly.
STATUS_LIVE = "LIVE"
STATUS_NEAR_REAL_TIME = "NEAR-REAL-TIME"
STATUS_FORECAST = "FORECAST"
STATUS_HISTORICAL = "HISTORICAL"
STATUS_STATIC = "STATIC"
STATUS_UNAVAILABLE = "UNAVAILABLE"


@dataclass
class SourcedValue:
    """A single data point carrying its own provenance and freshness.

    `value` is None exactly when the provider had nothing to report.
    Callers must never substitute 0 for a missing reading (SDR §5) —
    checking `.available` (or `value is None`) is the only correct test.
    """

    value: Any = None
    unit: str = ""
    source: str = ""
    status: str = STATUS_UNAVAILABLE
    timestamp: str | None = None
    note: str | None = None  # e.g. "Provider not configured" (SDR §18)

    @property
    def available(self) -> bool:
        return self.value is not None

    @classmethod
    def unavailable(cls, source: str, note: str = "No data available") -> "SourcedValue":
        return cls(value=None, source=source, status=STATUS_UNAVAILABLE, note=note)


@dataclass
class WaveData:
    height_m: SourcedValue
    direction_deg: SourcedValue
    period_s: SourcedValue


@dataclass
class WindData:
    speed_kn: SourcedValue
    direction_deg: SourcedValue
    gust_kn: SourcedValue


@dataclass
class CurrentData:
    speed_kn: SourcedValue
    direction_deg: SourcedValue


@dataclass
class SpeciesObservation:
    scientific_name: str
    common_name: str | None = None
    classification: str | None = None  # e.g. "shark/ray", "dolphin" — derived from OBIS taxonomy
    observed_on: str | None = None  # most recent OBIS eventDate seen for this species in the query, e.g. "2023-11-30"


@dataclass
class SpeciesResult:
    radius_km: float
    records: int
    species_count: int
    recent: list[SpeciesObservation] = field(default_factory=list)
    source: str = "OBIS"
    note: str | None = None


@dataclass
class WorldwideSpeciesPoint:
    """One real OBIS occurrence record, for the worldwide species-search
    map overlay — unlike SpeciesResult (aggregated species list around one
    clicked point), each point here is an individual sighting with its own
    coordinates, plotted directly on the map rather than shown in the sidebar."""

    scientific_name: str
    latitude: float
    longitude: float
    classification: str | None = None
    observed_on: str | None = None


@dataclass
class OceanData:
    latitude: float
    longitude: float

    # --- Phase 1 (SDR §9) ---
    depth_m: SourcedValue = field(default_factory=lambda: SourcedValue.unavailable("GEBCO"))
    seabed_elevation_m: SourcedValue = field(default_factory=lambda: SourcedValue.unavailable("GEBCO"))
    sea_surface_temperature_c: SourcedValue = field(default_factory=lambda: SourcedValue.unavailable("NOAA"))
    water_body: SourcedValue = field(default_factory=lambda: SourcedValue.unavailable("Marine Regions"))
    nearest_coast_distance_km: SourcedValue = field(default_factory=lambda: SourcedValue.unavailable("OpenStreetMap"))

    # --- Phase 2 (SDR §11-13) — None means "not queried" (layer off);
    # SourcedValue(status=UNAVAILABLE) inside means "queried, no data".
    waves: WaveData | None = None
    wind: WindData | None = None
    current: CurrentData | None = None
    salinity: SourcedValue | None = None
    sea_level_anomaly_cm: SourcedValue | None = None
    rain_mm: SourcedValue | None = None
    cloud_cover_pct: SourcedValue | None = None
    species: SpeciesResult | None = None
    fishing_activity_hours: SourcedValue | None = None
    marine_protected_area: SourcedValue | None = None
