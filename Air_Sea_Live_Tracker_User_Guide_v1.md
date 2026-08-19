# Air & Sea Live Tracker — User Guide & Operating Principles

Status: Phases 1–3 implemented (see SDR §29). Phases 4–5 (internet
enrichment, value estimation, alerts, true visibility, satellite
AIS/ADS-B, schedule APIs) are **not implemented** — see "What's not
built yet" at the end of this document for the honest gap list. The
separate **Ocean & Environment tab** (§1.8) is also implemented, under
its own spec — see `OpenHorizon_Ocean_Environment_SDR.md`.

---

## Part 1 — How to Use

### 1.1 Running the app

From the project root:

```
cd air_sea_tracker
../.venv/bin/python main.py
```

Or from PyCharm: use the existing **"AIRSEA (main)"** run configuration
(already checked in under `.idea/runConfigurations/`) — it points at
`air_sea_tracker/main.py` with the working directory set correctly.

Requirements are in `requirements.txt` at the repo root; install into
`.venv` with `pip install -r requirements.txt`.

### 1.2 First launch

On first run the observer location is unset (lat/lon fields start at
0,0) — there is no hardcoded default coordinate baked into source.
Type or paste a location and click **Set** to get started. After
that, your last-used location, radius, filters, map zoom, and theme
are restored automatically (SDR §27.3) — this app never starts you
from a blank slate on purpose once you've set one.

### 1.3 Nearby Mode (default view)

- **Set your location**: type into the Lat/Lon fields, or **paste a
  coordinate pair copied directly from Google Maps** (e.g.
  `43.5081, 16.4402`) into either field — it's detected and splits
  into both fields automatically. Click **Set** to apply.
- **Range**: slider or quick-pick chips (10/25/50/100/250/500 km).
  Changing the range only affects what's *displayed* and matched —
  the AIS/ADS-B providers stay subscribed to a fixed wide area (500 km)
  in the background so moving the slider never triggers a reconnect.
- **Air / Sea**: toggle which target types show.
  **Class A / Class B**: for vessels, toggle AIS transponder class
  (Class A = mandatory/commercial, Class B = lower-power/leisure).
  Only AISStream currently reports class; vessels from other providers
  are unclassified and always shown regardless of this filter.
- **Map**: click a marker to select it (highlights the matching table
  row and vice versa). Clustering is always on — it visually
  degrades to individual markers automatically once you're zoomed in
  enough that clusters would be misleading.
- **Table**: sortable by column. Select a row and press **Cmd+C**
  (or Ctrl+C) to copy the selected cells — including the Name column
  — as tab-separated text.
- **Target detail drawer**: click a marker/row to open it. Shows live
  telemetry (speed in km/h + mph, course, distance) plus identity and
  technical fields (MMSI/IMO/callsign/flag/dimensions for vessels;
  ICAO24/registration/type/origin country for aircraft). Click
  **Track History** to draw that target's recorded track as a line on
  the map (toggle again to clear it).

### 1.4 Global Mode

Same map+table pairing as Nearby, but shows the *entire* live cache
with no observer/radius restriction — just Air/Sea filters. Refreshes
every 5s (coarser than Nearby's 2s, since it's a much larger dataset).

### 1.5 History Mode

Pick a target from the dropdown (populated from everything that has
recorded history — click **Refresh list** if a target you just saw
isn't listed yet), pick a time range (Live/1h, 24h, 7 days), click
**Load**. Shows distance travelled, max/avg speed, and draws the
track on an embedded map.

Retention is configurable in Settings (§1.7) — default 7 days;
anything older is purged automatically on an hourly sweep.

### 1.6 Ports / Airports Mode

Requires an observer location to be set first (Nearby Mode). Shows the
nearest N ports/airports (1–20, default 5) from a bundled seed dataset
(see §2.5 for sourcing). Selecting one shows live traffic grouped by
inferred status:

- **Ports**: In port / Anchored / Approaching / Departing / Passing
  nearby, plus an **Inbound Radar** — a wider-radius scan for vessels
  whose course is roughly aimed at the port, independent of the
  port's own (much tighter) geofence.
- **Airports**: On/near ground / Approaching / Departing / Nearby.
  **This is observed ADS-B traffic only** — there is no scheduled-
  flight-data source wired up, so this is not a timetable.

### 1.7 Settings

**Data Sources**: enter/save API keys or credentials per AIS provider
(AISStream, BarentsWatch, AISHub, VesselAPI) — each is stored via the
OS keychain (`keyring`), never in a plaintext config file or QSettings.
Saving a credential automatically restarts the AIS provider set to
pick it up. OpenSky (ADS-B) needs no key on the anonymous free tier.
Also holds the optional **Global Fishing Watch** token used by the
Ocean & Environment tab's Fishing activity layer (§1.8) — the app
needs restarting after adding it for the layer's checkbox to unlock.

**Appearance**: theme (System/Light/Dark).

### 1.8 Ocean & Environment Mode

A separate global map for environmental/marine data, independent of
the observer/radius that drives Nearby Mode — full spec in
[`OpenHorizon_Ocean_Environment_SDR.md`](OpenHorizon_Ocean_Environment_SDR.md).

- **Layer Controls** (left panel): toggle map overlays and data-only
  layers by group — Ocean (bathymetry, depth contours, sea
  temperature), Geography (coastline, rivers, lakes), Dynamic (waves,
  currents, wind, rain, clouds, salinity, sea level, storms, sea ice),
  Marine (species observations, fishing activity, marine protected
  areas). A grayed-out checkbox with a tooltip means genuinely
  unavailable, not broken — hover it to see why (e.g. sea ice has no
  free source that can be queried or displayed the way every other
  layer here is; fishing activity needs a free Global Fishing Watch
  token from Settings first).
- **Click anywhere on the map** to query every enabled layer at that
  point; results populate the right-hand sidebar, each value tagged
  with its source and freshness (live/near-real-time/forecast/
  historical/static) — a field that's unavailable says so explicitly
  rather than showing a blank or a zero.
- **Time control** (top bar): scrub 24h back to 48h forward to see
  forecast/historical conditions for the time-varying layers (SST,
  wind, waves, rain, clouds, salinity, sea level). Static layers like
  bathymetry and coastline ignore it.
- **Species search**: with "Species observations" enabled, the
  sidebar lists species observed near the clicked point (OBIS
  records) with a last-observed date, filterable by a preset group
  (whales & dolphins / sharks & rays / lobsters & crabs / seabirds) or
  a typed scientific name.
- **"Use as observer location"** button (sidebar, under a clicked
  point's coordinates): jumps that point straight into Nearby Mode as
  the tracking observer.

**Worldwide species search** lives on the **Nearby** tab instead (next
to the observer panel), not the Ocean tab — it's a standalone
"go find whales/sharks/dolphins anywhere" tool independent of a
clicked point: pick a group (or type a scientific name), click
**Search worldwide**, and real OBIS sightings from the last 3 years
plot as color-coded dots on the map.

---

## Part 2 — Operating Principles

### 2.1 Data flow

```
        AIS PROVIDERS (concurrent)                 ADS-B
  AISStream  BarentsWatch  AISHub  VesselAPI       OpenSky
  (push/WS)   (poll/REST)  (poll)   (poll, metered) (poll, quota-limited)
        \        |           |        /                |
         \       |           |       /                 |
          v_______v___________v_____v                   v
              AISProviderManager               ADSBCollector
           (health tracking, free-first             |
            failover, silence detection)              |
                    \                                 /
                     v_______________________________v
                          TargetManager
                   (live cache, TTL, dedup,
                    history recording, filters)
                          |            |
                          v            v
                   LiveTargetCache   SQLite (batched, ~20s)
                   (in-memory, GUI    current_positions /
                    reads this)       position_history /
                                      vessels / aircraft
                          |
                          v
                    Map (Leaflet)  +  Table (Qt model)
```

Everything above the SQLite layer runs on the `qasync` event loop
alongside the Qt GUI loop — network I/O never blocks the UI thread
(SDR §24).

### 2.2 AIS provider architecture: free-first, health-tracked

Each provider (`services/ais_providers/*.py`) is a small state machine:
`DISABLED` (no credentials) → `CONNECTING` → `LIVE` (delivered a
packet within the last 45s) → `NO_DATA` (connected/subscribed but
gone silent) or `RATE_LIMITED` / `OFFLINE`.

They all run **concurrently**, not as a strict primary/fallback chain
— coverage differs by provider (e.g. BarentsWatch is Norway-only), so
running them together adds value rather than wasting it. The one
exception is VesselAPI (`is_free_tier = False`, hard 150-calls/month
budget): before every poll it checks whether any free-tier provider
is currently `LIVE` for the area and skips the call if so — spending
its metered budget only when the free tier isn't already covering.

The top bar's single "AIS" indicator is an aggregate across all
providers, prioritized `live > no_data > rate_limited > connecting >
offline > disabled` — it shows the most useful available signal
rather than one silent provider masking another that's actually live.

### 2.3 Caching — three layers, three different reasons

1. **Live in-memory cache** (`services/cache_service.py`): TTL-based
   (120s aircraft, 600s vessels). This is what the GUI actually reads
   every refresh tick. Expired entries drop off the map but remain in
   history.
2. **SQLite persistence** (`database/repository.py`,
   `TargetManager.flush_to_db`): the live cache is flushed to disk
   every ~20s and on app close, and reloaded on startup (respecting
   remaining TTL, so stale entries aren't resurrected as if fresh).
   This is why relaunching the app shows data immediately instead of
   an empty map, and why quota-limited providers don't need to be
   re-polled just to restore what was already known moments earlier.
3. **Persistent poll gates & quota counters**
   (`services/rate_limiter.py`): `PersistentPollGate` stops a
   REST-polling provider from firing an immediate call on every
   relaunch if it already called recently *for that location*
   (keyed by a coarse ~55km bucket, so a genuine location change via
   "Set" isn't blocked by a stale timer from somewhere else).
   `MonthlyRateLimiter` persists VesselAPI's call count across
   restarts. `RateLimiter.apply_backoff` persists a hard deadline
   parsed from a 429's real `Retry-After` header (OpenSky can hand
   out an hours-long one) — so a restart during a real block doesn't
   immediately retry and get blocked again.

### 2.4 Position history

Not every packet becomes a history row (SDR §26.5): a point is only
recorded if position moved ≥0.1km, heading changed ≥10°, speed changed
≥2kt, or ≥60s elapsed since the last recorded point for that target.
Retention is swept hourly against the configured
`history_retention_days` setting.

### 2.5 Ports/airports seed data — what it is and isn't

- **Airports**: OurAirports.com (CC0/public domain), filtered to
  `large_airport` + `medium_airport` (~5,272 of their ~85k rows —
  small strips/heliports excluded as out of scope).
- **Ports**: NGA World Port Index / Pub 150 (US government, public
  domain), ~3,800 major ports with surveyed coordinates.

Both were verified (license + direct download URL) before bundling —
see `database/seed.py` for the exact provenance notes. They load
once, only if the corresponding table is empty. **This is a static
seed, not a live-updating feed** — new/renamed ports and airports
won't appear without re-running the seed process against a fresh
source download.

### 2.6 Known limitations (read before assuming something is broken)

- **OpenSky (ADS-B)** is the anonymous free tier: 400 credits/day
  *and* a separate, much stricter per-IP server-side throttle that
  can block for hours if hit repeatedly (e.g. from many rapid test
  relaunches). The app respects and persists real block durations
  now, but cannot shorten them.
- **AISStream**: works correctly when the account/key is valid, but
  is currently unresolved on the account side — AISStream silently
  accepts a subscription and never forwards data for the keys tried
  so far, which looks identical to "no traffic" but isn't; this needs
  AISStream support, not a client-side fix.
- **AISHub** requires a username tied to *contributing* an AIS feed —
  it isn't a plain sign-up key, so it will likely stay `DISABLED` for
  most users.
- **BarentsWatch** only covers Norwegian waters/EEZ by design (their
  data policy, not a bug here).
- **Vessel/aircraft AIS class** is only populated from AISStream;
  other providers don't report it, so the Class A/B filter treats
  their vessels as always-shown.
- **Ports/Airports pages have no embedded map** — deliberately kept
  list/table-based (see §2.5); Nearby/Global/History all have maps.
- **Phase 4 & 5 are not implemented** — see the notice at the top of
  this document.
- **Ocean tab's free sources substitute for the original spec's named
  ones** where those need a paid/registered account (e.g. Copernicus
  Marine for salinity/sea level) — NOAA CoastWatch ERDDAP, EMODnet,
  and NOAA NHC cover the same ground for free, verified live against
  their real endpoints.
- **Sea ice has no working layer** — real NOAA/NSIDC near-real-time
  data exists, but it's only published on a polar-stereographic grid
  (not lat/lon), so it can't be point-queried or displayed the way
  every other Ocean layer is without implementing that grid's
  projection math from scratch.
- **Fishing activity (Global Fishing Watch)** needs a free account
  token from Settings (§1.7) — the app hasn't been tested against a
  real token, since that requires the user's own registered account.
  Marine protected areas needs no token (public UNEP-WCMC service).
- **Coastline/nearest-coast lookups (OpenStreetMap Overpass)** are a
  small set of independently-run public mirrors that can be
  unreachable from some networks (corporate firewalls, some security
  tools) — the app tries three mirrors, then backs off for 10 minutes
  rather than retrying and re-logging on every click. This is a
  network-level condition the app can't route around.
- **Ocean tab's basemap labels follow OpenStreetMap's local-language
  names** — outside Latin-script regions (e.g. Russia, China, the
  Middle East), place names render in the local script, not English.
  Forcing English would mean switching both maps from raster tiles to
  a vector-tile engine (MapLibre GL), which hasn't been done.

### 2.7 Where things live (quick map of the codebase)

```
air_sea_tracker/
├── main.py                     entry point, LiveDataController
├── config/                     Settings (QSettings) + credentials (keyring)
├── collectors/adsb_collector.py OpenSky poll loop
├── services/
│   ├── ais_providers/          AISStream/BarentsWatch/AISHub/VesselAPI
│   ├── ais_provider_manager.py concurrent runner + health aggregation
│   ├── target_manager.py       live cache, history, filters, nearby()
│   ├── geofence_service.py     port/airport traffic classification
│   ├── port_service.py / airport_service.py   nearest-N search
│   └── rate_limiter.py         quota + persistent backoff/poll-gate
├── database/
│   ├── database.py             schema + migrations + seed hook
│   ├── repository.py           read/write helpers
│   └── seed.py                 ports/airports CSV import
├── data/                       bundled seed CSVs (§2.5)
├── models/                     Vessel / Aircraft / Port / Airport dataclasses
├── ocean/                      Ocean & Environment tab (§1.8)
│   ├── providers/              one file per data source (GEBCO, NOAA SST,
│   │                           OSM/Overpass, OBIS, salinity, sea level,
│   │                           storms, depth contours, MPA, fishing activity, ...)
│   ├── layers/layer_registry.py  the one list every layer checkbox/tile builds from
│   ├── cache/ocean_cache.py    spatial TTL cache, per-data-kind lifetimes
│   ├── models/                 OceanData, SourcedValue, species/wave/wind dataclasses
│   └── ocean_controller.py     GUI -> providers orchestration + caching
└── gui/
    ├── pages/                  one file per nav item (nearby/global/history/ocean/...)
    ├── panels/                 observer panel, target detail drawer, ocean sidebar/
    │                           layers panel, worldwide species search panel
    ├── map/                    LiveMap + Leaflet map.html (Nearby/Global/History),
    │                           OceanMap + ocean_map.html (Ocean tab)
    ├── widgets/time_control.py Ocean tab's forecast/historical time scrubber
    └── tables/                 Qt table model + view
```
