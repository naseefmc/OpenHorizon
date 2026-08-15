# Software Design Requirements --- Air & Sea Live Tracker

## 1. Purpose

Build a cross-platform desktop application for **macOS and Windows**
that provides live tracking, filtering, history, port/airport
intelligence, and public-source enrichment for commercial aircraft,
private/business jets, helicopters, cargo aircraft, cargo ships,
tankers, ferries, cruise ships, yachts/superyachts, sailing vessels,
high-speed craft, fishing vessels, and other AIS/ADS-B targets.

The application combines **live ADS-B aviation data**, **live AIS
maritime data**, locally stored historical positions, geographic
calculations, data caching, persistent settings, and optional internet
enrichment.

## 1.1 Free-First Data Requirement

The MVP shall be fully usable without paid data subscriptions. Core live
tracking, map display, nearby search, filtering, local history, caching,
settings, port/airport discovery, and target photos shall use free/open
data sources wherever technically available.

Paid/commercial providers may be added later only as optional plug-ins
for improved coverage, schedules, satellite AIS/ADS-B, premium
historical data, or enrichment. Absence of a paid provider must not
disable the core application.

The UI shall identify the active source and gracefully handle
limitations in free-source coverage.

## 2. Target Platform

-   Windows 10/11
-   macOS Apple Silicon
-   Python 3.12+
-   Standalone packaged desktop application
-   No browser required for normal operation

Recommended stack: - Python - PySide6 / Qt for GUI - FastAPI or internal
Python services for data layer - SQLite for MVP - PostgreSQL/PostGIS
optional later - WebSocket clients for live feeds - Qt WebEngine + web
mapping layer - asyncio for continuous live updates

Qt WebEngine embeds Chromium to support the JS mapping layer, which
typically adds 150-300 MB to the packaged application. This tradeoff
(map flexibility vs. package size) is accepted for MVP; a native
Qt/QML map is a possible future alternative if package size becomes a
blocker.

### 2.1 Packaging & Distribution

-   Packaging tool: PyInstaller (or equivalent) producing a
    platform-native bundle.
-   macOS builds must be signed and notarized; an unsigned/unnotarized
    app is blocked by Gatekeeper by default.
-   Windows builds should be code-signed to avoid SmartScreen
    warnings.
-   An update mechanism (manual download or in-app update check) shall
    be defined before first public release.

## 3. Main Application Modes

The application shall contain: 1. **Nearby / Observer Mode** 2. **Global
Mode** 3. **Port Mode** 4. **Airport Mode** 5. **History Mode** 6.
**Search & Intelligence Mode** (reached via the "Search" nav item;
contains both global search and the per-target Intelligence/Research
view, §12)

## 4. Nearby / Observer Mode

The user provides: - Latitude - Longitude - Search radius - Units: km /
NM - Air / Sea / Both

The application continuously determines all tracked objects within the
defined radius.

The map shall show: - User location - Search-radius circle - Aircraft -
Ships - Direction of movement - Selected object's track

A synchronized live table shall show: - Distance - Object/name - Type -
Speed - Heading/course - Altitude for aircraft - Destination where
available - Last update

Rows shall be sortable and filterable. Clicking a row highlights its map
marker, and clicking a marker selects the table row.

## 5. Maritime Tracking

Initial live source: **AISStream or equivalent AIS feed**.

AISStream's free tier is sourced from terrestrial AIS receivers.
Reception is reliable roughly out to 200 km / ~100 NM off most
coastlines; vessels further offshore (mid-ocean transits) will not
appear. This is a permanent free-tier coverage limitation, not a
transient error, and shall be communicated to the user (see §26.6)
rather than presented as a data gap/bug. Satellite AIS is a paid
plug-in option for extending offshore coverage (§1.1).

Required vessel information where available: - MMSI - IMO - Vessel
name - Callsign - Latitude/longitude - Speed over ground - Course over
ground - Heading - Navigation status - Destination - ETA - Ship type -
Draught - Length/width - Flag - Last update

### Vessel Filters

-   Yacht / pleasure craft
-   Sailing yacht
-   Cargo
-   Container
-   Tanker
-   Passenger
-   Cruise
-   Ferry
-   Fishing
-   Tug
-   High-speed craft
-   Pilot vessel
-   SAR
-   Military/law-enforcement where identifiable
-   Unknown
-   All

Additional filters: - Minimum/maximum speed - Minimum/maximum vessel
length - Flag - Destination - Distance - Moving only - Anchored only

## 6. Aviation Tracking

Initial source: **OpenSky or alternative ADS-B source**.

OpenSky's anonymous/free REST tier is limited to 400 API credits per
day and 10-second time resolution, returning only the most recent
state vectors (no historical query). A full-globe poll consumes
multiple credits per call, so sustained sub-minute global polling is
not achievable on the free tier without an OpenSky account (4,000-8,000
credits/day) or a supplementary free source such as adsb.lol / adsb.fi.
Realistic free-tier refresh cadence and quota usage shall be surfaced
in Settings (§27.6) rather than assumed to be unlimited.

Required information where available: - ICAO24 - Callsign -
Registration - Aircraft type - Latitude/longitude - Altitude - Ground
speed - Vertical rate - Track/heading - Squawk - Origin country -
On-ground status - Last update

### Aircraft Filters

-   Commercial airliner
-   Business/private jet
-   Turboprop
-   General aviation
-   Helicopter
-   Cargo
-   Government
-   Military
-   Unknown

Additional filters: - Altitude - Speed - Distance - Aircraft model -
Registration - Callsign - Country

## 7. Global Mode

Global Mode shall display currently available worldwide air and maritime
traffic, subject to the coverage and refresh-rate limitations of the
active free-tier source (§5, §6). Global refresh cadence on free-tier
sources is realistically 30-60 seconds for aviation and near-real-time
(seconds) for AIS, not the 1-5 second cadence targeted for Nearby Mode
(§24); this distinction shall be visible to the user, not silently
smoothed over.

At wide zoom levels targets shall be clustered. As the user zooms in,
clusters progressively separate into individual targets.

The application shall use efficient map/WebGL/JavaScript marker
rendering rather than thousands of individual Qt widgets.

## 8. Track History

The application shall maintain its own historical position database.

Each received position shall include: - Target ID - Target type -
Timestamp - Latitude/longitude - Altitude if aircraft - Speed -
Heading/course - Destination where available - Source

Default retention: **7 days**.

Configurable retention: - 1 day - 3 days - 7 days - 30 days - Unlimited

Target detail shall support: - Live - 1 hour - 24 hours - 7 days

Statistics should include: - Distance travelled - Maximum speed -
Average speed - Ports/airports visited where determinable - Time
stationary - Last known location

## 9. Port & Airport Mode

The user enters a position or selects a saved/current location.

The software shall determine the closest ports, marinas, and airports.
Default result count is 5 and shall be configurable from 1--20.

## 10. Port Detail View

Selecting a port shall show: - Vessels in port - Anchored vessels -
Vessels approaching - Vessels departing - Nearby vessels - Expected
traffic where schedule/ETA data is available

A configurable geofence shall allow the software to infer: - Entered
port - Left port - Anchored - Approaching - Passing nearby

An **Inbound Radar** function should search a wider radius around the
port for vessels apparently heading toward the selected port.

## 11. Airport Detail View

Airport mode shall show: - Aircraft approaching - Aircraft departing -
Aircraft on/near ground - Nearby aircraft - Expected arrivals - Expected
departures

The UI shall distinguish **observed ADS-B traffic** from **scheduled
flight data**.

## 12. Intelligence / Internet Enrichment

A selected vessel or aircraft shall provide a **Research** function,
reached from the **Search & Intelligence** mode or from any target's
detail panel.

Concrete free/open sources for ownership, operator, and valuation data
are not yet finalized. Registry lookups (e.g. flag-state ship
registries, aviation registries) are generally free/public; ownership,
beneficial-ownership, and comparable-sale data are largely
proprietary/commercial and are not guaranteed to be available at €0.
Enrichment coverage should therefore be treated as best-effort and
Phase 4+ scope (§29), not an MVP guarantee, until concrete free sources
are identified and named here.

### Vessel Enrichment

Search using: 1. IMO 2. MMSI 3. Vessel name 4. Callsign 5. Flag

Target information: - Registered owner - Reported beneficial owner -
Operator - Management company - Builder/shipyard - Build year -
Length/beam - Gross tonnage - Flag - Home port - Previous names -
Charter information - Public sale listings - Estimated market value -
Recent news

Information shall include source attribution and confidence.

Ownership shall distinguish: - REGISTERED OWNER - REPORTED OWNER -
OPERATOR - MANAGEMENT COMPANY - UNVERIFIED CLAIM

Uncertain beneficial ownership must not be presented as confirmed fact.

## 13. Vessel Value Estimator

For vessels where sufficient information exists, estimate an approximate
market value range based on: - Builder - Build year - Length - Gross
tonnage - Vessel type - Refit year - Comparable listings - Known sales

Output shall include: - Estimated range - Confidence level - Number/list
of comparable vessels

The result must be labelled as an **estimate**, not a formal valuation.

Comparable-sale data for yachts/superyachts is largely held by
commercial brokerage sites, not free/open sources. If no free source of
comparable sales is identified, this feature shall be deferred or
scoped down (e.g. builder/length/age-based rough heuristic clearly
labeled as low-confidence) rather than implemented against scraped
commercial listing data without permission.

## 14. Aircraft Enrichment

Aircraft research shall attempt to determine: - Registration - ICAO24 -
Aircraft model - Manufacturer - Serial number - Build year - Registered
owner - Operator - Leasing company where public - Private/business use -
Estimated aircraft value - Estimated charter price - Recent publicly
reported movements/news

## 14.1 Vessel & Aircraft Photos --- Free-First Requirement

The target detail view shall display a **photo of the selected vessel or
aircraft when a suitable legally reusable image is available**. The MVP
shall not require a paid photo API.

### Free Photo Source Priority

1.  **Wikimedia Commons / MediaWiki API** as the primary source.
2.  Other explicitly open-licensed or public-domain image sources with
    clear attribution metadata.
3.  Locally cached previously resolved open-licensed image.
4.  Type-specific vector placeholder.

Commercial photo services may be supported later only as optional
provider plug-ins.

### Lookup

For vessels search by IMO, MMSI, exact vessel name + type, vessel name +
flag, then callsign. For aircraft search by registration, ICAO24 where
indexed, registration + model, then model + operator.

### Validation

Verify reusable/public-domain licensing, attribution requirements, and
target identity where possible. If match confidence is low, show the
placeholder rather than presenting an uncertain image as the actual
target.

### Display

Show a wide photo above primary telemetry. Clicking it opens a larger
preview with target name, source, creator/photographer, license, image
date where available, and source-page reference.

### Photo Cache

Cache the target identifier, thumbnail/reference where permitted, source
page, creator, license, retrieval timestamp, and match confidence.
Default validity: **30 days**. Avoid repeated downloads and provide
**Refresh Photo**.

### Missing Photos

Use polished vector placeholders for yachts, sailing vessels, cargo
ships, tankers, ferries, commercial aircraft, private jets, helicopters,
and unknown targets. A placeholder must clearly look like an
illustration.

### Licensing

Retain and display required attribution/license information. Do not
scrape or reuse copyrighted images without permission.

**Core requirement: target-photo functionality must remain usable at
€0.**

## 15. Object Detail Panel

All targets shall use a common detail panel containing: - Live
telemetry - Identity - Technical characteristics - Distance from
observer - Destination/ETA where available - History controls - Internet
research - Enrichment results - Confidence/source information

## 16. Map Requirements

Map shall support: - OpenStreetMap base layer - Zoom/pan/full-screen -
User position marker - Radius circle - Aircraft markers - Vessel
markers - Port markers - Airport markers - Historical track lines -
Heading arrows - Marker clustering

Optional layers: - Satellite imagery - Nautical map - Airport map - Dark
map

## 17. Marker Design

Marker classes shall visually distinguish aircraft and vessel types and
rotate according to heading/course where possible.

## 18. Distance Calculations

Observer distance shall use geographic great-circle distance.

The application shall provide: - Straight-line/great-circle distance -
Bearing from observer

Aircraft may additionally show: - Horizontal distance - Slant distance -
Altitude

## 19. True Visibility Mode

A future advanced mode shall distinguish simple **range** from
**geometric visibility**, using: - Observer altitude - Target altitude -
Earth curvature

## 20. Alerts

Users may define local alerts such as: - Private jet within X km -
Superyacht within X km - Vessel longer than X m within X km - Aircraft
below a specified altitude within X km - Specific MMSI detected -
Specific ICAO24 detected

### 20.1 Responsible Use & Opt-Out Handling

Per-tail-number alerting and owner/beneficial-owner enrichment on
private aircraft and yachts can identify and track specific
individuals' movements. This carries real safety, stalking, and
reputational risk (cf. the 2022 "ElonJet" private-jet tracking
controversy that led to platform bans, and the FAA's LADD program
allowing aircraft owners to opt out of public ADS-B display).

The application shall:

-   Honor published owner opt-out/block lists where technically
    feasible (e.g. FAA LADD-blocked tail numbers should not resolve to
    owner identity through the enrichment feature, even if raw ADS-B
    position data is still receivable).
-   Scope "reported beneficial owner" enrichment to what is already
    public-record information, and never present speculative
    ownership claims about a named private individual as confirmed
    (§12, ownership confidence labelling).
-   Treat specific-tail-number/specific-MMSI alerting as a
    power-user feature, not a default-on capability.

This policy shall be finalized before Phase 4 enrichment work begins.

## 21. Database

Recommended MVP database: **SQLite**.

Core tables: - targets - current_positions - position_history -
vessels - aircraft - ports - airports - enrichment - user_locations -
alerts

Primary tracking identifiers: - Aircraft → ICAO24 - Vessel → IMO where
available (stable, hull-based identifier), falling back to MMSI when no
IMO is known (e.g. small craft). MMSI alone is not a reliable long-term
key: MMSIs are reassigned, reused, and occasionally spoofed, so
MMSI-only correlation can silently merge the histories of two different
vessels. Vessel records shall retain both identifiers where known and
track MMSI changes against a stable internal target ID rather than
keying history purely on MMSI.

Position records should be indexed by target ID, timestamp, latitude,
and longitude.

## 22. Data Architecture

``` text
                 INTERNET
       ┌────────────┴─────────────┐
       │                          │
   ADS-B API                  AIS STREAM
       │                          │
       ▼                          ▼
 Aircraft Collector        Vessel Collector
       │                          │
       └────────────┬─────────────┘
                    ▼
                Normalizer
                    │
              ┌─────┴─────┐
              │           │
              ▼           ▼
          Live Cache    Database
                          │
                       History
                          │
                    Enrichment DB
                          │
                          ▼
                 Application Engine
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
              MAP                   TABLE
```

Note: AIS and ADS-B collectors use fundamentally different transport
models — AISStream delivers a persistent WebSocket push feed, while the
free OpenSky REST API is poll-based and quota-limited (§6). The
Aircraft Collector and Vessel Collector shall therefore implement
distinct control-flow (scheduled poll with backoff vs. long-lived
stream reader), not a shared polling loop. A dedicated Rate
Limiter/Quota Tracker service shall sit in front of poll-based sources,
track remaining daily quota, apply backoff on 429/rate-limit responses,
and expose current quota usage to the Application Engine and Settings
UI (§27.6).

## 23. GUI Structure

Primary navigation: - Global - Nearby - Ports - Airports - History -
Search & Intelligence - Settings

The main traffic views shall combine a large interactive map with a
synchronized live table.

## 24. Performance Requirements

-   GUI remains responsive during continuous updates
-   Network collection never executes on GUI thread
-   Map refresh approximately every 1--5 seconds in Nearby/Observer
    Mode with a live AIS/ADS-B feed; Global Mode refresh cadence is
    source-dependent and may be 30--60 seconds on free-tier aviation
    data (see §6-§7)
-   Table refresh may be independently throttled
-   Historical database writes shall be batched
-   Duplicate positions shall be filtered
-   Global map shall use clustering
-   Architecture should support at least 50,000 simultaneously cached
    targets

## 25. Export

Allow export of: - Selected vessel/aircraft - Nearby objects - Position
history - Port traffic

Formats: - CSV - JSON - GPX - KML

## 26. Data Caching

The application shall implement a multi-level cache to reduce API calls,
improve responsiveness, and support temporary network outages.

### 26.1 Live Target Cache

Maintain an in-memory cache for currently active aircraft and vessels.

Recommended cache keys: - `aircraft:{ICAO24}` - `vessel:{MMSI}`

Default stale/expiry targets: - Aircraft: 120 seconds - Vessel: 600
seconds

Expired targets disappear from the live map but remain in history.

### 26.2 API/Metadata Cache

Cache slower-changing information such as: - Aircraft registration/model
information - Vessel metadata - Port information - Airport information -
Owner/operator enrichment - Vessel/aircraft value estimates - Internet
research results

Suggested defaults: - Live position: 5--30 seconds - Vessel metadata: 7
days - Aircraft metadata: 7 days - Airport/port data: 30 days -
Owner/operator information: 24 hours - Market/value research: 7 days -
Web enrichment: 24 hours

Users shall be able to force-refresh enrichment.

### 26.3 Map Cache

Where permitted by the map provider, map tiles should be cached locally.
Provider caching/usage terms must be respected.

### 26.4 Position Write Buffer

Incoming positions shall first enter a memory buffer. Database writes
shall be batched, with a recommended configurable flush interval of
5--30 seconds.

### 26.5 Duplicate Filtering

The application shall avoid unnecessary history records when position,
speed, heading, and elapsed time changes are below configured
thresholds.

### 26.6 Offline Behaviour

If a source becomes unavailable: - Keep displaying recent cached
targets - Clearly mark stale data - Display age of last update -
Automatically reconnect - Keep GUI responsive - Preserve historical data

### 26.7 Cache Management

Settings shall display: - Cache size - Database size - Oldest cached
data - History retention

Controls: - Clear Live Cache - Clear Map Cache - Clear Enrichment
Cache - Clear Position History - Clear All Cached Data

Destructive actions require confirmation.

## 27. Persistent Application Settings

All user settings shall automatically persist between sessions.

Persist: - Last observer latitude/longitude - Last radius - Air/sea
filters - Last application mode - Map center/zoom/provider - History
retention - Units - API configuration - Window size/position - Column
widths - Table sorting/filtering - Cache settings - Refresh intervals

### 27.1 Settings Storage

Recommended implementation: **PySide6 QSettings** for
platform-appropriate persistent preferences (non-sensitive settings
only).

Larger cached datasets and historical data shall remain in the
application database/cache directories.

**API credentials must never be stored via QSettings or any plaintext
config file.** They shall be stored using OS-native secure storage
(e.g. the Python `keyring` package backed by macOS Keychain / Windows
Credential Locker) and must never be written into logs or exports.
This is a hard requirement, not a preference.

### 27.2 Save Behaviour

Settings shall be saved when changed and during application shutdown.
Critical settings should be persisted immediately rather than relying
solely on a clean shutdown.

### 27.3 Restore Last Session

Configurable option: - Restore previous session on startup

Restore: - Last mode - Location - Radius - Active filters - Map
center/zoom - Units - Table layout

### 27.4 Saved Locations

Users shall be able to: - Save current location - Name/rename location -
Delete location - Set default location - Quickly load saved locations

### 27.5 Saved Filter Profiles

Users shall be able to save reusable profiles such as: - All Traffic -
Yacht Watch - Private Aviation - Commercial Shipping

### 27.6 API Settings

A dedicated source configuration page shall contain: - AIS provider/API
key - ADS-B provider/credentials - Airport provider/API key - Port
provider/API key - Internet enrichment provider/API key

Each source should offer **Test Connection** and show: - Connected -
Authentication failed - Rate limit exceeded - Service unavailable

For quota-limited free-tier sources (e.g. OpenSky), this page shall
also display current quota usage (e.g. "128 / 400 credits used today")
sourced from the Rate Limiter/Quota Tracker service (§22), so users
understand why refresh cadence may degrade before the daily reset.

### 27.7 Data Status Indicator

The GUI should continuously show: - LIVE / CACHED / OFFLINE status -
Aircraft count - Vessel count - Last update age - Cache size - Database
size

## 28. Updated Cached Data Flow

``` text
                LIVE SOURCES
           AIS              ADS-B
            │                 │
            └───────┬─────────┘
                    ▼
               NORMALIZER
                    │
                    ▼
              LIVE MEMORY CACHE
                    │
        ┌───────────┼────────────┐
        ▼           ▼            ▼
       GUI      Position      Enrichment
                  Buffer          Cache
                    │              │
                    ▼              ▼
                 SQLite        Metadata DB
                    │
                    ▼
              7-Day History
```

Caching is a core application component, not an optional optimization.

## 29. MVP Development Stages

### Phase 1

-   Desktop GUI
-   Map
-   AIS live feed
-   ADS-B live feed
-   Nearby mode
-   Radius selection
-   Air/sea filters
-   Map/table synchronization
-   Persistent settings

### Phase 2

-   Local position-history database
-   Data caching
-   7-day tracks
-   Vessel/aircraft detail page
-   Global mode
-   Marker clustering

### Phase 3

-   Ports
-   Airports
-   Nearest-port/airport search
-   Port geofencing
-   In-port / approaching / departing logic
-   Inbound Radar

### Phase 4

-   Internet enrichment
-   Owners/operators
-   Yacht information
-   Aircraft information
-   Estimated values
-   Source/confidence handling

### Phase 5

-   Alerts
-   True horizon/visibility
-   Better schedule APIs
-   Satellite AIS/ADS-B providers
-   Advanced analytics

## 30. MVP Success Criteria

The first usable release is successful when a user can: 1. Start the
application on Mac or Windows. 2. Enter or restore a latitude/longitude.
3. Select a radius. 4. See live aircraft and vessels within that radius.
5. Filter yachts, ships, private jets and other classes. 6. View targets
simultaneously on a map and sortable table. 7. Click a target to inspect
telemetry. 8. View stored movement history. 9. Switch to a global
traffic map. 10. Find nearby ports and airports. 11. Inspect live
traffic around those locations. 12. Perform public-source enrichment on
a selected vessel or aircraft. 13. Retain settings across application
restarts. 14. Use cached metadata and recent target information to
reduce API usage.

## 31. Recommended Project Structure

``` text
air_sea_tracker/
│
├── main.py
├── gui/
│   ├── main_window.py
│   ├── nearby_tab.py
│   ├── global_tab.py
│   ├── port_tab.py
│   ├── airport_tab.py
│   ├── history_tab.py
│   ├── target_details.py
│   └── settings_dialog.py
├── collectors/
│   ├── ais_collector.py
│   └── adsb_collector.py
├── services/
│   ├── target_manager.py
│   ├── geo_service.py
│   ├── port_service.py
│   ├── airport_service.py
│   ├── enrichment_service.py
│   ├── cache_service.py
│   └── value_estimator.py
├── database/
│   ├── database.py
│   ├── models.py
│   └── migrations/
├── maps/
│   ├── map_controller.py
│   └── markers.py
├── models/
│   ├── aircraft.py
│   ├── vessel.py
│   ├── port.py
│   └── airport.py
├── config/
│   ├── settings.py
│   └── credentials.py
└── utils/
    ├── distance.py
    ├── units.py
    └── logging.py
```

The architecture shall separate data providers from the GUI so
OpenSky/AISStream can later be replaced or supplemented by commercial
ADS-B, satellite AIS, flight schedule, port-call, and enrichment
providers without rewriting the user interface.
