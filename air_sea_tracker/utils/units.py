"""Unit conversions (SDR §4: km / NM)."""

KM_PER_NM = 1.852
MPH_PER_KT = 1.150779
MS_PER_KT = 0.514444


def km_to_nm(km: float) -> float:
    return km / KM_PER_NM


def nm_to_km(nm: float) -> float:
    return nm * KM_PER_NM


def kt_to_kmh(knots: float) -> float:
    return knots * KM_PER_NM


def kmh_to_kt(kmh: float) -> float:
    return kmh / KM_PER_NM


def kt_to_mph(knots: float) -> float:
    return knots * MPH_PER_KT


def mph_to_kt(mph: float) -> float:
    return mph / MPH_PER_KT


def ms_to_kt(ms: float) -> float:
    return ms / MS_PER_KT


def kt_to_ms(knots: float) -> float:
    return knots * MS_PER_KT


def m_to_ft(meters: float) -> float:
    return meters * 3.28084


def ft_to_m(feet: float) -> float:
    return feet / 3.28084


def speed_label(knots: float | None) -> str:
    """Formats a speed stored in knots (the shared internal unit for both
    vessels and aircraft — see TargetManager) as km/h and mph together."""
    if knots is None:
        return "—"
    return f"{kt_to_kmh(knots):.0f} km/h · {kt_to_mph(knots):.0f} mph"
