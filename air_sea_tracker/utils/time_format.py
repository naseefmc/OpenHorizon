"""Timestamp display helpers — when a readout is actually from (SDR §4, §15)."""

from __future__ import annotations

from datetime import datetime, timezone


def age_label(last_update: datetime | None) -> str:
    """Short relative age for table cells, e.g. 'live', '42s ago', '3m ago'."""
    if last_update is None:
        return "—"
    now = datetime.now(timezone.utc)
    ts = last_update if last_update.tzinfo else last_update.replace(tzinfo=timezone.utc)
    age = (now - ts).total_seconds()
    if age < 5:
        return "live"
    if age < 60:
        return f"{int(age)}s ago"
    if age < 3600:
        return f"{int(age // 60)}m ago"
    return f"{int(age // 3600)}h ago"


def timestamp_with_age(last_update: datetime | None) -> str:
    """Full local-time readout for detail panels, e.g. '14:02:11 (42s ago)' —
    the actual wall-clock time the position/telemetry is from, not just a
    relative age that keeps sliding as you look at it."""
    if last_update is None:
        return "—"
    ts = last_update if last_update.tzinfo else last_update.replace(tzinfo=timezone.utc)
    local = ts.astimezone()
    return f"{local.strftime('%H:%M:%S')} ({age_label(last_update)})"
