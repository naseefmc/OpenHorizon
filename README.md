# OpenHorizon — Air & Sea Live Tracker

Cross-platform desktop app (PySide6) for live tracking of aircraft and
vessels around an observer location, built free-first on public AIS/ADS-B
data sources, with local history, port/airport intelligence, and
best-effort public-source enrichment. Also includes a separate **Ocean &
Environment tab** — click anywhere on a global map for bathymetry, sea
temperature, salinity, sea level, coastline, weather, species observations,
marine protected areas, and more, all from free public sources.

## Disclaimer

OpenHorizon AirSea is a non-commercial hobby project created for informational, educational, and demonstration purposes.

The software and all displayed or aggregated data are provided **"as is" and "as available," without warranties of any kind**, express or implied. This includes warranties of accuracy, reliability, availability, merchantability, fitness for a particular purpose, and non-infringement.

AIS, ADS-B, aircraft, vessel, weather, map, and enrichment data originate from third-party providers or public sources. This information may be delayed, incomplete, inaccurate, outdated, unavailable, estimated, or incorrectly identified.

**OpenHorizon AirSea is not a certified navigation, air-traffic-control, vessel-traffic, collision-avoidance, flight-planning, voyage-planning, or emergency-response system.** It must not be relied upon for navigation, operational decisions, safety-critical purposes, surveillance, or emergencies. Always use official and approved aviation or maritime information sources.

To the maximum extent permitted by applicable law, the project owner, authors, and contributors shall not be liable for any loss, damage, injury, claim, or other consequence arising from:

* the use, misuse, or inability to use the software;
* reliance on information displayed by the software;
* inaccurate, delayed, incomplete, or unavailable data; or
* third-party data, APIs, services, or content.

Third-party data and services remain subject to their respective licences, terms of service, privacy policies, and usage restrictions. The open-source licence for this project does not grant any rights to third-party data. Users are responsible for ensuring that their use of the software and its data complies with applicable laws and provider terms.

Unless otherwise stated, the original OpenHorizon AirSea source code is available under the **MIT License or the Apache License 2.0, at the user's option (`MIT OR Apache-2.0`)**. The complete licence terms are provided in `LICENSE-MIT` and `LICENSE-APACHE`. If this disclaimer conflicts with either licence, the applicable licence takes precedence.

## Status

Phases 1–3 of the SDR are implemented and working: live Nearby/Global
map+table, multi-provider AIS with health/failover, ADS-B via OpenSky,
position history, Ports/Airports modes with geofence-based traffic
classification, and Search. Phase 4 is partial (vessel enrichment via
Wikidata works; aircraft enrichment via the FAA registry is wired but
unverified; value estimates are an explicitly-labeled rough heuristic).
Phase 5 is mostly not started — Alerts, satellite AIS/ADS-B, and
schedule APIs remain to be built. See
[`Air_Sea_Live_Tracker_User_Guide_v1.md`](Air_Sea_Live_Tracker_User_Guide_v1.md)
for the full "what's implemented / what's not" breakdown.

The **Ocean & Environment tab** is implemented per its own spec
([`OpenHorizon_Ocean_Environment_SDR.md`](OpenHorizon_Ocean_Environment_SDR.md)):
bathymetry, depth contours, sea temperature, coastline/rivers/lakes,
water body naming, waves/currents/wind/rain/clouds, salinity, sea level
anomaly, storms, species observations (local + worldwide search), and
marine protected areas — all free, keyless sources. Fishing activity
needs a free Global Fishing Watch token (Settings); sea ice has no
working free source (see the User Guide's Known Limitations for why).

## Quick start

```bash
cd air_sea_tracker
pip install -r ../requirements.txt
python main.py
```

On first launch, go to **Settings → Data Sources** and add API keys/
credentials for whichever AIS providers you want (AISStream, BarentsWatch,
VesselAPI, AISHub — all free-tier, none required to run the app). OpenSky
(ADS-B) works anonymously with no key, subject to its free-tier rate
limits. The same Settings page has an optional Global Fishing Watch token
for the Ocean tab's Fishing activity layer (also free-tier, also not
required — every other Ocean layer works with no key at all).

## Documentation

- [**User Guide & Operating Principles**](Air_Sea_Live_Tracker_User_Guide_v1.md) —
  how to use every mode (including the Ocean tab), and how the
  provider/caching architecture works under the hood.
- [**Software Design Requirements**](Air_Sea_Live_Tracker_SDR_v2.md) — the
  original spec the air/sea tracker is built against.
- [**Ocean & Environment SDR**](OpenHorizon_Ocean_Environment_SDR.md) — the
  original spec the Ocean tab is built against.
- [**GUI Design Guide**](Air_Sea_Live_Tracker_GUI_Design_Guide_v2.md) —
  visual/interaction design reference.

## Project layout

See the "Where things live" section of the User Guide for a map of the
`air_sea_tracker/` package (collectors, AIS providers, services, database,
`ocean/` providers, GUI pages).

## License / data attribution

App code is dual-licensed under MIT OR Apache-2.0 — see `LICENSE-MIT` and
`LICENSE-APACHE`. Bundled seed data:
- `air_sea_tracker/data/airports_seed.csv` — [OurAirports.com](https://ourairports.com/data/), Public Domain/CC0.
- `air_sea_tracker/data/ports_seed.csv` — NGA World Port Index (Pub 150), US government public domain.

The Ocean tab's optional fishing-activity layer is "Powered by
[Global Fishing Watch](https://globalfishingwatch.org)". That data is
made available under GFW's [CC BY-NC 4.0 terms of
use](https://globalfishingwatch.org/our-apis/documentation#license-and-rate-limits)
— noncommercial use only, subject to their daily/monthly API rate
limits, using a token you register and configure yourself (Settings →
Data Sources). It is not covered by this project's MIT/Apache-2.0
licence, which applies to the app's own source code only.
