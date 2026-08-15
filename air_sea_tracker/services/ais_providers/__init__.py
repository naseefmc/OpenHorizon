"""Pluggable AIS data sources with independent health tracking (SDR §5, §22).

Each provider parses its own wire format into the shared `Vessel` model
and is run concurrently by `AISProviderManager`, which also demotes a
provider from LIVE to NO_DATA if it goes quiet for too long even while
its connection stays open (e.g. AISStream accepting a subscription but
never forwarding packets for an unauthenticated key).
"""
