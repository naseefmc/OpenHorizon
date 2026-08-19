"""Registry of every toggleable Ocean & Environment map layer (SDR §4, §11).

Each entry pairs a stable layer id (shared by the Layer Controls
checkboxes and the JS map bridge) with the provider that owns its tile
config. The layer panel and the map widget both build themselves off
this one list, so adding a layer means adding one LayerDef here.

One Phase 1 item doesn't get its own tile source: "Rivers" and "Lakes"
are two checkboxes over one combined ERDDAP boundary layer (see
osm_water.RiversLakesProvider) — there's no free source that splits them.
"""

from __future__ import annotations

from dataclasses import dataclass

from ocean.providers.base import OceanProvider, TileLayerSpec
from ocean.providers.depth_contours import DepthContourProvider
from ocean.providers.fishing_activity import FishingActivityProvider
from ocean.providers.gebco import GebcoProvider
from ocean.providers.marine_protected_areas import MarineProtectedAreaProvider
from ocean.providers.noaa_sst import NoaaSstProvider
from ocean.providers.osm_water import CoastlineProvider, RiversLakesProvider
from ocean.providers.salinity import SalinityProvider
from ocean.providers.sea_level import SeaLevelProvider
from ocean.providers.storms import StormsProvider

GROUP_OCEAN = "OCEAN"
GROUP_GEOGRAPHY = "GEOGRAPHY"
GROUP_DYNAMIC = "DYNAMIC"
GROUP_MARINE = "MARINE"


@dataclass
class LayerDef:
    layer_id: str
    label: str
    group: str
    provider: OceanProvider | None
    default_on: bool = False
    phase: int = 1
    unavailable_reason: str | None = None  # set to disable the checkbox and explain why

    @property
    def available(self) -> bool:
        # `provider` here means "owns a map tile" — several real, working
        # Phase 2 layers (waves/currents/wind/rain/clouds/marine_life) are
        # data-only with no WMS/XYZ overlay to show, so they legitimately
        # have provider=None while still being fully queryable.
        #
        # When a provider exists, IT decides availability (e.g. a credential-
        # gated one like fishing_activity can start unavailable and flip to
        # available once a key is added in Settings — unavailable_reason on
        # such a layer is informational tooltip text only, not a static
        # override). unavailable_reason only forces availability off by
        # itself for the true hard stubs that have no provider at all.
        if self.provider is not None:
            return self.provider.is_available()
        return not self.unavailable_reason

    def tile_spec(self) -> TileLayerSpec | None:
        return self.provider.get_layer() if self.provider else None


def build_layers() -> list[LayerDef]:
    """Fresh LayerDef list with fresh provider instances — call once per
    OceanController, not per render, since providers are cheap but the
    controller is the single owner of layer state."""
    gebco = GebcoProvider()
    noaa_sst = NoaaSstProvider()
    coastline = CoastlineProvider()
    rivers_lakes = RiversLakesProvider()
    depth_contours = DepthContourProvider()
    salinity = SalinityProvider()
    sea_level = SeaLevelProvider()
    storms = StormsProvider()
    fishing_activity = FishingActivityProvider()
    mpa = MarineProtectedAreaProvider()

    return [
        # --- Phase 1: OCEAN ---
        LayerDef("bathymetry", "Bathymetry", GROUP_OCEAN, gebco, default_on=True, phase=1),
        LayerDef("depth_contours", "Depth contours", GROUP_OCEAN, depth_contours, phase=1),
        LayerDef("sea_temperature", "Sea temperature", GROUP_OCEAN, noaa_sst, phase=1),
        # --- Phase 1: GEOGRAPHY ---
        LayerDef("coastline", "Coastline", GROUP_GEOGRAPHY, coastline, phase=1),
        LayerDef("rivers", "Rivers", GROUP_GEOGRAPHY, rivers_lakes, phase=1),
        LayerDef("lakes", "Lakes", GROUP_GEOGRAPHY, rivers_lakes, phase=1),
        # --- Phase 2: DYNAMIC (SDR §11) ---
        LayerDef("waves", "Waves", GROUP_DYNAMIC, None, phase=2),
        LayerDef("currents", "Ocean currents", GROUP_DYNAMIC, None, phase=2),
        LayerDef("wind", "Wind", GROUP_DYNAMIC, None, phase=2),
        LayerDef("rain", "Rain", GROUP_DYNAMIC, None, phase=2),
        LayerDef("clouds", "Clouds", GROUP_DYNAMIC, None, phase=2),
        LayerDef("salinity", "Salinity", GROUP_DYNAMIC, salinity, phase=2),
        LayerDef("sea_level", "Sea level", GROUP_DYNAMIC, sea_level, phase=2),
        LayerDef("storms", "Storms", GROUP_DYNAMIC, storms, phase=2),
        LayerDef(
            "sea_ice", "Sea ice", GROUP_DYNAMIC, None, phase=2,
            unavailable_reason=(
                "No free source with a usable point-query or map overlay — NSIDC/OSI-SAF sea-ice "
                "data exists but is only published on a polar-stereographic grid, not lat/lon, so "
                "it can't be queried or displayed the way every other layer here is"
            ),
        ),
        # --- Phase 2: MARINE (SDR §13, §11) ---
        LayerDef("marine_life", "Species observations", GROUP_MARINE, None, phase=2),
        LayerDef(
            "fishing_activity", "Fishing activity", GROUP_MARINE, fishing_activity, phase=2,
            unavailable_reason="Requires a free Global Fishing Watch API key — add one in Settings > Data Sources",
        ),
        LayerDef("marine_protected_areas", "Marine protected areas", GROUP_MARINE, mpa, phase=2),
    ]
