# OpenHorizon — Air & Sea Live Tracker

Cross-platform desktop app (PySide6) for live tracking of aircraft and
vessels around an observer location, built free-first on public AIS/ADS-B
data sources, with local history, port/airport intelligence, and
best-effort public-source enrichment.

## Disclaimer

This repository, its code, and any data it displays or aggregates are
provided **"as is," with no warranty of any kind**. Unauthorized use of
this software or of the data it surfaces is not permitted. The repository
owner assumes **no legal responsibility** for:

- the accuracy, completeness, timeliness, or reliability of any
  tracking/positional data displayed by this app;
- any use, misuse, or unauthorized use of this repository, its code, or
  its data by any third party;
- any consequences, direct or indirect, arising from reliance on this
  software or its output.

AIS/ADS-B and enrichment data are pulled from third-party providers (see
[Quick start](#quick-start) and the User Guide); each provider's own
terms of service govern permitted use of their data, and it is the
user's responsibility to comply with them.

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
limits.

## Documentation

- [**User Guide & Operating Principles**](Air_Sea_Live_Tracker_User_Guide_v1.md) —
  how to use every mode, and how the provider/caching architecture works
  under the hood.
- [**Software Design Requirements**](Air_Sea_Live_Tracker_SDR_v2.md) — the
  original spec this app is built against.
- [**GUI Design Guide**](Air_Sea_Live_Tracker_GUI_Design_Guide_v2.md) —
  visual/interaction design reference.

## Project layout

See the "Where things live" section of the User Guide for a map of the
`air_sea_tracker/` package (collectors, AIS providers, services, database,
GUI pages).

## License / data attribution

App code has no license file yet — no license is granted for reuse; all
rights reserved by default. See the Disclaimer above. Bundled seed data:
- `air_sea_tracker/data/airports_seed.csv` — [OurAirports.com](https://ourairports.com/data/), Public Domain/CC0.
- `air_sea_tracker/data/ports_seed.csv` — NGA World Port Index (Pub 150), US government public domain.
