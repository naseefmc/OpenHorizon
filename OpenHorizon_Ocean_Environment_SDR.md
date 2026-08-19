# OpenHorizon -- Ocean & Environment Tab

## Software Design Requirements (SDR)

**Project:** OpenHorizon AirSea\
**Feature:** Global Ocean & Environment Tab\
**Implementation:** Two phases

------------------------------------------------------------------------

## 1. Purpose

Add a new **Ocean & Environment** tab to OpenHorizon that provides
global environmental, geographic, and marine information alongside
existing aircraft and vessel tracking.

The tab shall allow users to:

-   Enable and disable environmental map layers.
-   Click anywhere on the map and retrieve data for that location.
-   Display selected-location information in a sidebar.
-   Combine environmental data with vessel information.
-   Support global coverage.
-   Clearly distinguish live, near-real-time, forecast, historical, and
    static datasets.

------------------------------------------------------------------------

## 2. Proposed GUI

``` text
┌──────────────────────────────────────────────────────────────┐
│ OpenHorizon                                                  │
│ Air | Sea | Ocean & Environment                              │
├──────────────────────────────────────────────┬───────────────┤
│                                              │ LOCATION INFO │
│                  MAP                         │               │
│                                              │ Lat / Lon     │
│    Bathymetry / SST / Waves / Currents       │ Depth         │
│                                              │ SST           │
│            ● clicked point                   │ Waves         │
│                                              │ Wind          │
│                                              │ Current       │
│                                              │ Salinity      │
├──────────────────────────────────────────────┴───────────────┤
│ Layers: ☑ Depth ☐ SST ☐ Waves ☐ Currents ☐ Wind            │
└──────────────────────────────────────────────────────────────┘
```

Existing vessel and aircraft markers may remain visible so environmental
information can be viewed in context.

------------------------------------------------------------------------

# Phase 1 -- Global Ocean Fundamentals

## 3. Phase 1 Goal

Establish the global map-layer architecture and click-to-query
framework.

## 4. Phase 1 Features

  Feature                   Requirement                   Proposed Source
  ------------------------- ----------------------------- -----------------
  Global bathymetry         Colored seabed depth map      GEBCO
  Point depth               Depth at clicked location     GEBCO
  Coastline                 Global coastline              OpenStreetMap
  Rivers                    Rivers and streams            OpenStreetMap
  Lakes/water bodies        Inland water                  OpenStreetMap
  Sea Surface Temperature   SST heatmap and point value   NOAA
  Map click                 Query selected position       Internal
  Sidebar                   Display returned values       Internal

### Layer Controls

``` text
OCEAN
☑ Bathymetry
☐ Depth contours
☐ Sea temperature

GEOGRAPHY
☐ Coastline
☐ Rivers
☐ Lakes
```

Only one heavy raster/heatmap layer should be active by default to limit
rendering and network load.

------------------------------------------------------------------------

## 5. Map Click Behaviour

Every map click shall generate a selected-location event:

``` python
SelectedLocation(
    latitude,
    longitude,
    timestamp
)
```

The Ocean Controller shall request all enabled/required information for
that position.

Example sidebar:

``` text
LOCATION

Latitude        42.95621°
Longitude       17.13784°

OCEAN

Depth           84 m
SST             24.1 °C

GEOGRAPHY

Water body      Adriatic Sea
Nearest coast   3.8 km

DATA

Depth source    GEBCO
SST source      NOAA
SST timestamp   19 Aug 2026 09:00 UTC
```

Unavailable data shall be displayed explicitly:

``` text
Sea Temperature
No data available
```

The application shall not substitute zero for unavailable data.

------------------------------------------------------------------------

## 6. Bathymetry

Primary global dataset: **GEBCO**.

Requirements:

-   Global coverage.
-   Land and ocean elevation.
-   Colored raster overlay.
-   Point depth lookup.
-   Depth contours.

Suggested depth bands:

``` text
0–20 m
20–50 m
50–100 m
100–200 m
200–500 m
500–1000 m
1000–3000 m
3000–6000+ m
```

Sidebar:

``` text
Depth          428 m
Elevation     -428 m
Source         GEBCO
```

The UI shall display:

> Approximate bathymetric data. Not for navigation.

------------------------------------------------------------------------

## 7. Sea Surface Temperature

The application shall provide a global SST overlay and point-query
result.

Example:

``` text
Sea Surface Temperature
24.6 °C

Observation
19 Aug 2026 09:00 UTC

Source
NOAA
```

SST shall be independently switchable from bathymetry.

------------------------------------------------------------------------

## 8. Phase 1 Software Architecture

Suggested structure:

``` text
openhorizon/
│
├── ocean/
│   ├── ocean_tab.py
│   ├── ocean_controller.py
│   │
│   ├── providers/
│   │   ├── gebco.py
│   │   ├── noaa_sst.py
│   │   └── osm_water.py
│   │
│   ├── layers/
│   │   ├── bathymetry_layer.py
│   │   ├── sst_layer.py
│   │   ├── coastline_layer.py
│   │   └── river_layer.py
│   │
│   ├── models/
│   │   ├── ocean_location.py
│   │   └── ocean_data.py
│   │
│   └── cache/
│       └── ocean_cache.py
```

API-specific logic shall not be implemented directly in the GUI.

``` text
GUI
 ↓
OceanController
 ↓
Provider abstraction
 ↓
GEBCO / NOAA / OSM
```

------------------------------------------------------------------------

## 9. Unified Ocean Data Model

``` python
OceanData:
    latitude
    longitude

    depth_m
    seabed_elevation_m

    sea_surface_temperature_c

    water_body
    nearest_coast_distance_km

    depth_source
    temperature_source

    temperature_timestamp
```

Phase 2 shall extend this model with dynamic environmental parameters.

------------------------------------------------------------------------

# Phase 2 -- Dynamic Ocean & Marine Intelligence

## 10. Phase 2 Goal

Transform the tab from a geographic viewer into a global environmental
situational-awareness interface.

## 11. Phase 2 Layers

  Layer                    Type                        Typical Freshness
  ------------------------ --------------------------- -------------------
  Waves                    Near-real-time / forecast   Hours
  Ocean currents           Near-real-time              Hours
  Wind                     Near-real-time / forecast   Hours
  Salinity                 Near-real-time              Hours/day
  Sea level                Near-real-time              Hours
  Rain                     Near-real-time              Minutes/hours
  Clouds                   Near-real-time              Minutes/hours
  Storms                   Near-real-time              Minutes/hours
  Sea ice                  Near-real-time              Hours/day
  Marine observations      Historical/recent           Variable
  Fishing activity         Delayed                     Days
  Marine protected areas   Static                      Periodic

Primary environmental provider: **Copernicus Marine**, supplemented by
NOAA where appropriate.

------------------------------------------------------------------------

## 12. Phase 2 Sidebar

Example:

``` text
OCEAN CONDITIONS

Depth
428 m

Sea surface temperature
24.6 °C

Waves
Height          1.4 m
Direction       235°
Period          6.8 s

Wind
Speed           14.2 kn
Direction       NW
Gust            19.1 kn

Current
Speed           0.42 kn
Direction       SE

Salinity
38.1 PSU

Sea level anomaly
+4.2 cm
```

------------------------------------------------------------------------

## 13. Marine Life

Add optional marine-life layers:

``` text
MARINE LIFE

☐ Fish observations
☐ Sharks
☐ Whales
☐ Dolphins
☐ Sea turtles
☐ Coral
```

Primary source: **OBIS**.

Example click result:

``` text
SPECIES OBSERVATIONS

Radius          10 km
Records         284
Species         47

Recent observations

Common dentex
Gilthead seabream
European seabass
Atlantic mackerel
```

The UI shall use wording such as **"Species observed nearby"** rather
than **"Fish currently here"**, because biodiversity observations are
not real-time animal tracking.

------------------------------------------------------------------------

## 14. Time Control

Phase 2 shall introduce a common environmental timeline.

``` text
Past ─────────●──────── Future

19 Aug 2026
12:00 UTC
```

The time control may drive:

-   SST
-   Wind
-   Waves
-   Currents
-   Rain
-   Sea level

The architecture should permit vessel tracks to use the same time
reference later.

------------------------------------------------------------------------

## 15. Vessel Integration

The Ocean Controller shall also support environmental lookup around
selected AIS vessels.

Example:

``` text
VESSEL

SEA BREEZE
MMSI 238XXXXXX

Navigation

Speed          8.4 kn
Course         124°

Environment

Water depth    84 m
SST            23.8 °C
Waves          1.2 m
Wind           14 kn NW
Current        0.6 kn SE
```

Map-click and vessel-click environmental queries shall reuse the same
controller and provider implementations.

------------------------------------------------------------------------

## 16. Provider Interface

All providers should follow a common abstraction.

``` python
class OceanProvider:

    def get_point_data(self, lat, lon):
        ...

    def get_layer(self, bounds, zoom):
        ...

    def is_available(self):
        ...
```

Example implementations:

``` text
GebcoProvider
NoaaSSTProvider
CopernicusProvider
ObisProvider
OSMProvider
```

This allows providers to be replaced or extended without rewriting the
GUI.

------------------------------------------------------------------------

## 17. Caching

Caching shall be implemented to reduce API traffic and improve
responsiveness.

  Data                   Suggested Cache
  ---------------------- -----------------
  Bathymetry             Days/months
  Coastline              Days
  Rivers                 Days
  SST                    1--6 hours
  Waves                  1--3 hours
  Currents               1--3 hours
  Wind                   30--60 minutes
  Species observations   24 hours

Spatial cache keys may use rounded coordinates:

``` python
round(lat, 3)
round(lon, 3)
```

Repeated clicks within approximately the same area should reuse cached
data where appropriate.

------------------------------------------------------------------------

## 18. Error Handling

Each provider shall fail independently.

Example:

``` text
Depth              84 m
SST                24.1 °C
Wave data          Unavailable
Current            0.5 kn
```

Failure of one external service shall not make the Ocean & Environment
tab unusable.

Timeouts, malformed responses, HTTP failures, authentication failures,
and missing data shall be handled gracefully.

------------------------------------------------------------------------

## 19. Data Status and Freshness

Dynamic results shall indicate freshness/status.

``` text
● LIVE
● 2 h old
● Forecast +3 h
● Historical
● Static
```

This is required because AIS, weather, SST, bathymetry, fishing
activity, and species observations represent fundamentally different
data timelines.

------------------------------------------------------------------------

## 20. Phase 1 Delivery

Implement:

1.  Ocean & Environment tab.
2.  Layer manager.
3.  GEBCO global bathymetry.
4.  Colored bathymetry overlay.
5.  Click-to-depth lookup.
6.  Depth contours.
7.  NOAA SST overlay.
8.  Click-to-SST lookup.
9.  OSM coastline.
10. OSM rivers/lakes.
11. Location sidebar.
12. Provider abstraction.
13. Caching.
14. Error handling.
15. Source and timestamp display.

------------------------------------------------------------------------

## 21. Phase 2 Delivery

Implement:

1.  Wave height, direction, and period.
2.  Wind speed, direction, and gusts.
3.  Ocean-current speed and direction.
4.  Salinity.
5.  Sea-level/anomaly.
6.  Rain and cloud layers.
7.  Storm information.
8.  Sea ice.
9.  OBIS marine-life observations.
10. Fishing activity.
11. Marine protected areas.
12. Environmental information for selected AIS vessels.
13. Environmental time slider.
14. Historical/forecast selection.
15. Unified freshness/status indicators.

------------------------------------------------------------------------

## 22. Final Architecture

``` text
                    OpenHorizon
                         │
             Ocean & Environment Tab
                         │
              ┌──────────┴──────────┐
              │                     │
            MAP                  SIDEBAR
              │                     │
              └──── OceanController ┘
                         │
                 Provider Manager
                         │
        ┌────────┬───────┼───────┬─────────┐
        │        │       │       │         │
      GEBCO     NOAA   Copernicus OSM     OBIS
        │        │       │       │         │
      Depth      SST    Ocean    Geo      Marine
                       Weather            Life
```

------------------------------------------------------------------------

## 23. Future Extension

The architecture shall leave room for later derived/intelligence
features such as:

-   Environmental conditions around a moving vessel.
-   Sailing-condition assessment.
-   Wave-risk indicators.
-   Species likelihood based on depth, SST, season, and observations.
-   Historical environmental playback.
-   Route environmental profiling.
-   Environmental alerts.
-   Additional regional high-resolution bathymetry providers.

These functions are outside the initial two-phase implementation but
should not require redesign of the core provider/controller
architecture.
