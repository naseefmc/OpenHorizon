# Air & Sea Live Tracker --- GUI Design Guide

## 1. Design Vision

The GUI should feel like a modern **live intelligence/radar
application**, but remain simple enough that a first-time user
immediately understands what to do.

Design principles:

-   **Map first** --- the live world is the main interface.
-   **Progressive detail** --- show essential information first; reveal
    technical detail on click.
-   **Fast scanning** --- color, icons, typography, and spacing should
    make aircraft/vessels recognizable instantly.
-   **Low clutter** --- avoid dense engineering-tool layouts.
-   **Consistent interaction** --- clicking a marker, table row, port,
    airport, or search result always opens the same style of detail
    panel.
-   **Light + Dark mode** --- both are first-class themes.
-   **Responsive desktop layout** --- optimized for laptops, large
    monitors, Windows, and macOS.

------------------------------------------------------------------------

# 2. Overall Layout

Recommended desktop structure:

``` text
┌─────────────────────────────────────────────────────────────────────────────┐
│  AIRSEA                                            ● LIVE     🔔   ⚙   ◐   │
├──────────┬─────────────────────────────────────────────────────┬────────────┤
│          │                                                     │            │
│  🌍      │                                                     │  SELECTED  │
│ Global   │                                                     │  TARGET    │
│          │                                                     │            │
│  ◎       │                    LIVE MAP                         │  Aurora    │
│ Nearby   │                                                     │  Yacht     │
│          │                                                     │            │
│  ⚓      │                                                     │  12.4 kn   │
│ Ports    │                                                     │  238°      │
│          │                                                     │  Hvar      │
│  ✈      │                                                     │            │
│ Airports │                                                     │ [Details]  │
│          │                                                     │ [7d Track] │
│  ◷       │                                                     │ [Research] │
│ History  │                                                     │            │
│          ├─────────────────────────────────────────────────────┴────────────┤
│  🔎      │  FILTERS            LIVE TARGETS                     247 found   │
│ Search   ├──────────────────────────────────────────────────────────────────┤
│          │ Type     Name        Dist.     Speed      Heading    Destination │
│          │ 🛥 Yacht  Aurora      4.2 km    12.4 kn    238°       Hvar        │
│  ⚙       │ ✈ Jet    D-ABCD      22 km     412 kt     164°       Split       │
│ Settings │ 🚢 Cargo MSC...      31 km     17.2 kn    291°       Venice      │
└──────────┴──────────────────────────────────────────────────────────────────┘
```

### Layout proportions

-   Left navigation: **72--88 px collapsed**, \~220 px expanded.
-   Map: approximately **65--75%** of usable workspace.
-   Bottom live table: **25--35%** of height and vertically resizable.
-   Right detail drawer: **320--400 px**, displayed only when needed.

The map should never feel boxed into a small panel.

------------------------------------------------------------------------

# 3. Navigation

Use a vertical icon navigation rail.

Primary modes:

-   🌍 **Global**
-   ◎ **Nearby**
-   ⚓ **Ports**
-   ✈ **Airports**
-   ◷ **History**
-   🔎 **Search** (Search & Intelligence Mode — global search plus the
    per-target Research/Intelligence view, §15)
-   ⚙ **Settings**

The currently selected mode uses a subtle filled background and accent
indicator.

Avoid traditional desktop menu-heavy interfaces.

Use conventional menus only for:

-   File/export
-   Advanced settings
-   Help/about

------------------------------------------------------------------------

# 4. Top Bar

Keep the top bar minimal.

``` text
AIRSEA     Split, Croatia ▼       ● LIVE     AIS  ●    ADS-B ●      🔔  ⚙  ◐
```

Recommended elements:

-   Application logo/name
-   Current observer location
-   Overall data status
-   AIS status
-   ADS-B status
-   Alerts
-   Settings
-   Light/Dark/System theme button

Status colors:

-   Green → live/healthy
-   Amber → delayed/cached
-   Red → disconnected/error
-   Gray → disabled

Do not rely on color alone; always include text/icon state.

------------------------------------------------------------------------

# 5. Nearby Mode

Nearby should be the simplest screen.

A floating search/range control sits over the map:

``` text
┌──────────────────────────────────────────────┐
│ ◎ Observer                                   │
│ Split, Croatia                       Change  │
│                                              │
│ Range  ─────●──────────────  100 km          │
│                                              │
│ [ Air ✓ ]  [ Sea ✓ ]      [ More filters ]  │
└──────────────────────────────────────────────┘
```

Users should be able to:

-   Type coordinates.
-   Search a location.
-   Click the map.
-   Use current position.
-   Select a saved location.

Radius adjustment should support both:

-   Slider
-   Numeric entry

Useful quick chips:

`10 km` `25 km` `50 km` `100 km` `250 km` `500 km`

------------------------------------------------------------------------

# 6. Map Design

The map is the visual centerpiece.

OpenStreetMap (and any other tile provider used) requires visible
attribution on the map; this must remain legible in both light and
dark map themes and must not be hidden behind floating controls.

Free-tier AIS coverage is limited to roughly 200 km / ~100 NM off most
coastlines (SDR §5). Rather than silently omitting offshore vessels,
consider a subtle shaded "reception limit" indicator on Global Mode so
the absence of mid-ocean traffic reads as a known coverage boundary,
not a bug.

## Target markers

Do not use oversized emoji markers in production. Use clean vector
icons.

Suggested shapes:

-   Commercial aircraft → aircraft silhouette
-   Private jet → smaller swept-wing aircraft
-   Helicopter → helicopter silhouette
-   Cargo vessel → ship
-   Tanker → tanker
-   Yacht → yacht silhouette
-   Sailing yacht → sailboat
-   Ferry → passenger vessel
-   Fishing → fishing vessel

Markers rotate according to heading/course.

### Marker behavior

Normal:

``` text
       ▲
```

Hovered:

``` text
┌────────────────────┐
│ AURORA             │
│ Yacht • 12.4 kn    │
│ 4.2 km away        │
└────────────────────┘
        ▲
```

Selected targets receive a visible selection halo.

Historical tracks should appear only for selected targets unless the
user explicitly enables multiple tracks.

------------------------------------------------------------------------

# 7. Map Controls

Use a compact floating control stack:

``` text
┌───┐
│ + │
│ − │
├───┤
│ ◎ │  Center observer
├───┤
│ ◈ │  Layers
├───┤
│ ⛶ │  Fullscreen
└───┘
```

Layer menu:

-   Standard
-   Dark
-   Satellite
-   Nautical
-   Aviation
-   Ports/Airports
-   Observer range
-   Tracks

------------------------------------------------------------------------

# 8. Live Target Table

The table should feel more like a modern data explorer than a
spreadsheet.

Default columns:

  ------------------------------------------------------------------------
   Target Type Distance Speed Heading Altitude/Status Destination Updated
  ------------------------------------------------------------------------

------------------------------------------------------------------------

Features:

-   Sort by any column.
-   Search instantly.
-   Pin columns.
-   Resize columns.
-   Hide/show columns.
-   Filter directly from column headers.
-   Double-click → full detail.
-   Single click → select marker.
-   Hover row → subtly highlight corresponding map marker.

Use alternating backgrounds only very subtly.

Avoid heavy grid lines.

------------------------------------------------------------------------

# 9. Quick Filters

Place filters immediately above the table.

Example:

``` text
[ All 247 ] [ ✈ Air 83 ] [ 🚢 Sea 164 ]

[ Private Jet ] [ Yacht ] [ Cargo ] [ Ferry ] [ Helicopter ]   + Filters
```

Selected filters use the accent color.

Advanced filter drawer:

``` text
TYPE
☑ Yacht
☑ Sailing
☐ Cargo
☐ Tanker

DISTANCE
0 ─────────────● 100 km

SPEED
Min [ 5 ]   Max [ Any ]

VESSEL LENGTH
Min [ 20 m ]

STATUS
☑ Moving
☑ Anchored

                    [ Reset ] [ Apply ]
```

------------------------------------------------------------------------

# 10. Target Detail Drawer

Clicking a target slides a panel in from the right.

Do not open separate windows.

``` text
╭────────────────────────────────╮
│  AURORA                    ×   │
│  Superyacht • Cayman Islands   │
│                                │
│        ● LIVE                  │
│                                │
│  12.4 kn       238°            │
│  SPEED         COURSE          │
│                                │
│  4.2 km        HVAR            │
│  DISTANCE      DESTINATION     │
│                                │
│ ────────────────────────────── │
│ LIVE                           │
│ Position     43.32, 16.72      │
│ MMSI         319xxxxxx         │
│ IMO          98xxxxx           │
│ Updated      3 sec ago         │
│                                │
│ [ ◷ 7 DAY TRACK ]              │
│ [ 🔎 RESEARCH ]                │
│                                │
│ ────────────────────────────── │
│ INTELLIGENCE                   │
│ Builder      Feadship          │
│ Year         2019              │
│ Length       74 m              │
│ Value        €70–90M           │
│ Confidence   MEDIUM            │
╰────────────────────────────────╯
```

Use large numerical telemetry at the top and detailed metadata below.

------------------------------------------------------------------------

# 11. Historical Track UI

When **7 Day Track** is selected, the map enters Track Mode.

``` text
AURORA — TRACK HISTORY

[ 1h ] [ 24h ] [ 3d ] [ 7d ]

──────●──────────────────────────────
Aug 8                              Aug 15

Distance travelled       842 km
Average speed             10.8 kn
Maximum speed             21.2 kn
Ports visited             6
```

The timeline slider should allow the user to scrub through movement.

A moving marker follows the historical path as the timeline changes.

------------------------------------------------------------------------

# 12. Global Mode

Global mode should emphasize visual exploration.

``` text
GLOBAL LIVE

42,581 targets

[ AIR 18,403 ] [ SEA 24,178 ]

                  WORLD MAP
```

At global zoom:

-   Cluster targets.
-   Show density.
-   Avoid rendering every label.
-   Reveal individual objects progressively while zooming.

Filters remain accessible without leaving the map.

------------------------------------------------------------------------

# 13. Port Mode

Port Mode should feel like a live operations board.

``` text
PORTS NEAR YOU

⚓ Split
2.8 km

21 In Port       6 Approaching
3 Departing     12 Expected

[ OPEN PORT ]
```

Nearest ports appear as horizontally scrollable cards or a compact list
beside the map.

Opening a port:

``` text
PORT OF SPLIT

● LIVE

[ Overview ] [ In Port ] [ Arrivals ] [ Departures ] [ Expected ]

21              6               3
IN PORT         APPROACHING     DEPARTING

──────────────────────────────────────────

                 PORT MAP

──────────────────────────────────────────

VESSEL       TYPE       STATUS          ETA
Aurora       Yacht      In Port          —
Jadro        Ferry      Approaching     13:42
...
```

------------------------------------------------------------------------

# 14. Airport Mode

Mirror the Port Mode interaction pattern.

``` text
SPLIT AIRPORT — SPU

● LIVE

[ Overview ] [ Arrivals ] [ Departures ] [ Nearby ]

8 Arrivals       11 Departures
4 Approaching     3 Nearby
```

Clearly label:

`OBSERVED`

versus

`SCHEDULED`

to prevent inferred ADS-B information being mistaken for official flight
schedules.

------------------------------------------------------------------------

# 15. Intelligence / Research View

Internet research should feel separate from raw tracking telemetry.

Use sections:

``` text
INTELLIGENCE

Identity
Ownership
Operator
Specifications
Market Value
News
Sources
```

Every claim can carry a confidence indicator:

-   **HIGH**
-   **MEDIUM**
-   **LOW**
-   **UNVERIFIED**

Example:

``` text
Reported Owner

Example Holdings Ltd.

Confidence: MEDIUM
3 public sources agree

[ View Sources ]
```

Never make uncertain ownership look authoritative. Where an aircraft
or vessel is on a published owner opt-out/block list (e.g. FAA LADD),
the Intelligence view shall omit owner-identity resolution for that
target rather than infer or display it (SDR §20.1).

------------------------------------------------------------------------

# 15.1 Target Photo Experience

When a suitable free/open-licensed photo is available, use it as a
strong visual identity element in the selected-target drawer without
allowing it to dominate live telemetry.

``` text
╭────────────────────────────────────╮
│          [ TARGET PHOTO ]          │
│  AURORA                            │
│  Superyacht • Cayman Islands       │
├────────────────────────────────────┤
│  12.4 kn      238°       4.2 km    │
│  SPEED        COURSE      DISTANCE │
╰────────────────────────────────────╯
```

-   Use a wide thumbnail with rounded upper corners.
-   Preserve aspect ratio; never stretch.
-   Clicking opens a larger preview.
-   Provide subtle source/creator/license attribution.
-   Cache thumbnails where permitted.
-   Never show broken-image icons.
-   Photo loading must never delay live telemetry.
-   If no verified free/open image exists, show a premium theme-aware
    vector illustration matching the target class.
-   Do not show locked photo areas, upgrade banners, or paid-photo
    prompts in the default GUI.
-   Optional commercial providers, if ever supported, belong only in
    advanced Data Source settings.

# 16. Search

Provide one global search field accessible with:

**Ctrl/Cmd + K**

Search:

-   Vessel name
-   MMSI
-   IMO
-   Aircraft registration
-   ICAO24
-   Callsign
-   Airport
-   Port
-   City
-   Saved location

Example:

``` text
╭──────────────────────────────────────────────╮
│ 🔎 Search aircraft, vessels, ports...        │
├──────────────────────────────────────────────┤
│ VESSELS                                     │
│ Aurora                 Yacht                │
│                                              │
│ AIRCRAFT                                    │
│ D-ABCD                 Citation XLS         │
│                                              │
│ PORTS                                       │
│ Port of Split          Croatia              │
╰──────────────────────────────────────────────╯
```

------------------------------------------------------------------------

# 17. Light Mode

Light mode should be warm-neutral rather than pure white everywhere.

### Core palette

  Role                     Suggested Color
  ------------------------ -----------------
  Application background   `#F6F8FB`
  Primary surface          `#FFFFFF`
  Secondary surface        `#EEF2F7`
  Primary text             `#172033`
  Secondary text           `#64748B`
  Border                   `#DCE3EC`
  Primary accent           `#2563EB`
  Secondary accent         `#06B6D4`
  Success / Live           `#16A34A`
  Warning / Cached         `#F59E0B`
  Error                    `#DC2626`
  Selection                `#DBEAFE`

The visual identity should primarily use **deep blue + cyan**, fitting
aviation, maritime, maps, and live-data visualization.

------------------------------------------------------------------------

# 18. Dark Mode

Dark mode should use deep blue/slate rather than pure black.

### Core palette

  Role                     Suggested Color
  ------------------------ -----------------
  Application background   `#0B1120`
  Primary surface          `#111827`
  Elevated surface         `#172033`
  Secondary surface        `#1E293B`
  Primary text             `#F1F5F9`
  Secondary text           `#94A3B8`
  Border                   `#293548`
  Primary accent           `#3B82F6`
  Secondary accent         `#22D3EE`
  Success / Live           `#22C55E`
  Warning / Cached         `#FBBF24`
  Error                    `#F87171`
  Selection                `#1E3A5F`

Dark mode should be particularly attractive for live tracking and large
map displays.

------------------------------------------------------------------------

# 19. Target Category Colors

Use category colors sparingly.

Suggested semantic system:

-   Aircraft → blue family
-   Private/business aviation → violet accent
-   Maritime → cyan/teal family
-   Yacht → turquoise accent
-   Commercial shipping → blue-gray
-   Port → teal
-   Airport → blue
-   Alert → amber
-   Critical/error → red

Color must **not** be the only distinction between categories. Icon
shape and labels remain primary.

------------------------------------------------------------------------

# 20. Typography

Recommended:

### Windows

**Segoe UI Variable**

### macOS

**SF Pro / system font**

Qt should use the platform system font by default.

Typography hierarchy:

``` text
Page title            24–28 px / Semibold
Section title         16–18 px / Semibold
Primary telemetry     22–30 px / Semibold
Normal UI             13–15 px / Regular
Table                  12–14 px / Regular
Metadata               11–12 px / Medium
```

Avoid excessive bold text.

------------------------------------------------------------------------

# 21. Shapes and Spacing

Use an **8 px spacing system**.

Typical spacing:

-   4 px → very tight relationships
-   8 px → controls
-   16 px → normal component spacing
-   24 px → sections
-   32 px → major separation

Corner radius:

-   Buttons: 8 px
-   Inputs: 8 px
-   Cards: 10--12 px
-   Floating panels: 12--16 px

Avoid excessive rounded "bubble" UI.

------------------------------------------------------------------------

# 22. Buttons

Primary:

``` text
[ Start Live Tracking ]
```

Secondary:

``` text
[ Show Track ]
```

Tertiary:

``` text
Research
```

Danger:

``` text
[ Clear History ]
```

Only one visually dominant primary action should normally exist within a
panel.

------------------------------------------------------------------------

# 23. Motion & Animation

Animations should communicate state, not decorate the UI.

Recommended:

-   Detail drawer slide: 150--220 ms
-   Filter drawer: 150--200 ms
-   Marker movement: smooth interpolation
-   Hover transitions: 100--150 ms
-   Theme transition: subtle

Live status may use a very gentle pulse.

Avoid flashing targets.

------------------------------------------------------------------------

# 24. Loading States

Never freeze the UI with a spinner covering the whole application.

Use localized loading states:

``` text
AIS
● Connecting...

ADS-B
● Live

Enrichment
Searching public sources...
```

Tables can use skeleton rows while loading.

Map remains interactive.

------------------------------------------------------------------------

# 25. Cached / Offline Visualization

Live state:

`● LIVE · Updated 2 sec ago`

Cached:

`◐ CACHED · Last live update 4 min ago`

Offline:

`○ OFFLINE`

Targets using stale data should become visually subdued.

Hover should clearly state:

`Last received 6 minutes ago`

------------------------------------------------------------------------

# 26. Empty States

Avoid blank screens.

Example:

``` text
No yachts within 25 km

Try increasing the range or removing filters.

[ Increase to 50 km ]
```

Port mode:

``` text
No port traffic currently detected.

AIS reception may be limited in this area.
```

------------------------------------------------------------------------

# 27. Settings Design

Settings should use categories rather than one enormous form.

``` text
SETTINGS

General
Appearance
Tracking
Data Sources
Cache & Storage
Map
Units
Alerts
Privacy
Advanced
```

### Appearance

``` text
Theme

(●) System
( ) Light
( ) Dark

Map theme
[ Match application ▼ ]

Density
Comfortable ───●── Compact
```

### Data Sources

Use cards:

``` text
AISSTREAM
● Connected

Live maritime tracking

API Key     •••••••••••••

[ Test Connection ]       [ Configure ]
```

For quota-limited sources (e.g. OpenSky), show remaining daily quota on
the card:

``` text
OPENSKY
● Connected

Live aviation tracking (ADS-B)

Quota       128 / 400 credits today
API Key     •••••••••••••

[ Test Connection ]       [ Configure ]
```

------------------------------------------------------------------------

# 28. Cache & Storage UI

Provide a visual overview:

``` text
CACHE & STORAGE

Position History         1.42 GB
Map Cache                  382 MB
Metadata                    84 MB
Enrichment                  26 MB
────────────────────────────────
Total                     1.91 GB

History retention
[ 7 Days ▼ ]

[ Clear Map Cache ]

[ Manage Storage ▾ ]
  Clear Live Cache
  Clear Map Cache
  Clear Enrichment Cache
  Clear Position History
  Clear All Cached Data
```

"Manage Storage" expands into the full set of clear actions defined in
SDR §26.7. Destructive actions (Clear Position History, Clear All
Cached Data) require a confirmation dialog.

Do not make users manage SQLite files manually.

------------------------------------------------------------------------

# 29. First Launch Experience

Keep onboarding extremely short.

### Screen 1

``` text
Welcome to AIRSEA

Live aircraft and vessel intelligence
from one map.

[ Get Started ]
```

### Screen 2

Configure sources:

``` text
AIRCRAFT
OpenSky
[ Configure ]

VESSELS
AISStream
[ Configure ]
```

### Screen 3

Choose observer:

``` text
Use my location

or

Latitude  [           ]
Longitude [           ]

[ Start Tracking ]
```

Then immediately open Nearby Mode.

------------------------------------------------------------------------

# 30. Keyboard Shortcuts

Recommended:

  Shortcut         Action
  ---------------- ------------------------
  `Ctrl/Cmd + K`   Global search
  `Ctrl/Cmd + L`   Observer/location
  `Ctrl/Cmd + F`   Filter
  `Ctrl/Cmd + ,`   Settings
  `Esc`            Close drawer/dialog
  `Space`          Center selected target
  `G`              Global mode
  `N`              Nearby mode
  `P`              Port mode

Do not trigger single-letter shortcuts while the user is typing in an
input.

------------------------------------------------------------------------

# 31. Responsive Desktop Behaviour

### Large monitor

Show:

`Navigation + Map + Detail Drawer + Table`

### Laptop

Show:

`Collapsed Navigation + Map + Table`

Detail panel overlays/slides over the right side.

### Small window

Allow table to collapse:

``` text
[ MAP ]
────────
[ ▲ 247 Targets ]
```

The application should remain usable at approximately **1280 × 720**.

------------------------------------------------------------------------

# 32. Accessibility

-   Maintain strong text/background contrast.
-   Never encode status using color alone.
-   Provide keyboard navigation.
-   Visible focus states.
-   Tooltips for icon-only buttons.
-   Allow UI scaling.
-   Respect operating-system font scaling where practical.
-   Avoid tiny map controls.
-   Minimum normal interactive target approximately 36--40 px.

------------------------------------------------------------------------

# 33. Theme Architecture

Do not hard-code colors throughout PySide6 widgets.

Create semantic theme tokens:

``` text
background
surface
surface_elevated
surface_hover

text_primary
text_secondary
text_muted

border
accent
accent_hover

live
warning
error

aircraft
private_aviation
vessel
yacht
```

Then provide:

``` text
LightTheme
DarkTheme
```

This makes switching themes instantaneous and keeps custom widgets
consistent.

------------------------------------------------------------------------

# 34. Recommended PySide6 Component Architecture

``` text
gui/
├── main_window.py
├── theme/
│   ├── theme_manager.py
│   ├── light_theme.py
│   ├── dark_theme.py
│   └── icons.py
│
├── navigation/
│   ├── sidebar.py
│   └── topbar.py
│
├── map/
│   ├── live_map.py
│   ├── map_bridge.py
│   └── map_controls.py
│
├── panels/
│   ├── target_drawer.py
│   ├── filter_drawer.py
│   └── observer_panel.py
│
├── tables/
│   ├── target_table.py
│   └── target_model.py
│
├── pages/
│   ├── global_page.py
│   ├── nearby_page.py
│   ├── ports_page.py
│   ├── airports_page.py
│   ├── history_page.py
│   ├── search_page.py
│   └── settings_page.py
│
└── widgets/
    ├── status_badge.py
    ├── stat_card.py
    ├── filter_chip.py
    ├── search_box.py
    └── telemetry_widget.py
```

Use Qt's model/view architecture for large live tables rather than
creating a widget for every cell.

------------------------------------------------------------------------

# 35. Visual Identity

The application should visually communicate:

**Ocean + Sky + Live Intelligence**

Suggested brand direction:

``` text
AIRSEA
LIVE TRACKER
```

or simply:

``` text
AIRSEA
```

Logo concept:

A minimal circular radar/orbit mark combining an aircraft wing and
vessel/wave motif.

The interface should feel closer to a modern flight tracker, marine
intelligence dashboard, and premium mapping application than to a
traditional engineering configuration GUI.

------------------------------------------------------------------------

# 36. Final UX Rule

At any moment the user should be able to answer three questions within a
few seconds:

1.  **What is around me / this location?**
2.  **What is this aircraft or vessel?**
3.  **Where has it been and what do we know about it?**

Every GUI decision should make those three tasks faster.
