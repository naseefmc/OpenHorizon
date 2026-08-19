"""Open-Meteo Forecast API provider — wind, rain, and clouds (Ocean & Environment SDR §11).

Same Copernicus-substitution rationale as open_meteo_marine.py: free,
keyless, global near-real-time/forecast data in place of the SDR's
named Copernicus Marine / NOAA sources for these layers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiohttp

from ocean.models.ocean_data import STATUS_FORECAST, STATUS_NEAR_REAL_TIME, SourcedValue, WindData
from ocean.providers.base import DEFAULT_TIMEOUT, USER_AGENT, OceanProvider

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_FIELDS = "wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation,cloud_cover"
KMH_TO_KN = 0.539957


def _nearest_index(times: list[str], when: datetime | None) -> int | None:
    if not times:
        return None
    target = (when or datetime.now(timezone.utc)).replace(tzinfo=None, minute=0, second=0, microsecond=0)
    best_i, best_diff = 0, None
    for i, t in enumerate(times):
        diff = abs((datetime.fromisoformat(t) - target).total_seconds())
        if best_diff is None or diff < best_diff:
            best_i, best_diff = i, diff
    return best_i


def _status_for(times: list[str], index: int) -> str:
    dt = datetime.fromisoformat(times[index])
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return STATUS_FORECAST if dt > now else STATUS_NEAR_REAL_TIME


class OpenMeteoWeatherProvider(OceanProvider):
    name = "Open-Meteo"

    async def get_point_data(self, lat: float, lon: float, when: datetime | None = None) -> dict:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": HOURLY_FIELDS,
            "timezone": "UTC",
            "past_days": 1,
            "forecast_days": 3,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    FORECAST_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
        except Exception:
            logger.exception("Open-Meteo forecast query failed")
            unavailable = SourcedValue.unavailable(self.name, "Open-Meteo forecast service unreachable")
            return {
                "wind": WindData(unavailable, unavailable, unavailable),
                "rain_mm": unavailable,
                "cloud_cover_pct": unavailable,
            }

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        idx = _nearest_index(times, when)
        if idx is None:
            unavailable = SourcedValue.unavailable(self.name, "No forecast data at this point")
            return {
                "wind": WindData(unavailable, unavailable, unavailable),
                "rain_mm": unavailable,
                "cloud_cover_pct": unavailable,
            }

        status = _status_for(times, idx)
        timestamp = times[idx] + ":00Z"

        def sv(field: str, unit: str, kmh_to_kn: bool = False) -> SourcedValue:
            values = hourly.get(field, [])
            value = values[idx] if idx < len(values) else None
            if value is None:
                return SourcedValue.unavailable(self.name, "No data at this hour")
            if kmh_to_kn:
                value = value * KMH_TO_KN
            return SourcedValue(value=round(value, 1), unit=unit, source=self.name, status=status, timestamp=timestamp)

        wind = WindData(
            speed_kn=sv("wind_speed_10m", "kn", kmh_to_kn=True),
            direction_deg=sv("wind_direction_10m", "°"),
            gust_kn=sv("wind_gusts_10m", "kn", kmh_to_kn=True),
        )

        return {
            "wind": wind,
            "rain_mm": sv("precipitation", "mm"),
            "cloud_cover_pct": sv("cloud_cover", "%"),
        }
