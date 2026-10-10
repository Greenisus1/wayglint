# Wayglint

Fullscreen terminal maps for Linux and SSH. Install and go: no API key, signup, billing account or paid fallback. Original app, not Google Maps or a Google product. You can export a Google Maps route link to open on your phone, without calling Google's API.

## What it does

- Explicit place search using Photon, with a five-result chooser.
- OpenStreetMap map tiles rendered as terminal color blocks, zoom and pan.
- OSRM/FOSSGIS driving route estimates and text maneuver steps.
- Locally saved favorite places, route link export and local response caching.
- `--offline` uses only previously cached requests and map tiles. No network calls. Cached routes can be old.
- `--demo` shows clearly marked generated demo art, not a real map.

This is a planning/exploration app, not live navigation. No GPS tracking, live traffic, closure/weather information or safety guarantees. Route estimates can be wrong or stale. Don't operate it while driving. Map street labels lose detail in terminal rendering. The visible map is one loaded tile, not a seamless multi-tile atlas. Panning/zooming changes the desired center; M fetches that chosen tile explicitly, never prefetches.

## Controls

S search; Up/Down choose and Enter select. C enter latitude,longitude. M fetch one map tile. Arrows pan desired center; +/- zoom. O marks current place as origin; select destination and R requests a driving route. Up/Down scroll steps, Esc returns to map. F saves a favorite; B lists favorites. G saves a Google Maps route link locally; `python3 wayglint.py --last-link` prints it for copying to your phone. H help. Q quits. Letter controls accept upper/lowercase. Terminal minimum: 80x23, 256 colors recommended.

## Install

Pi App Store discovers this repo in Apps. Its reviewed installer installs Python 3, Pillow and CA certificates through apt/apk/pacman only when missing. Arch installation can upgrade the whole system and asks pacman's normal prompt. Run `python3 wayglint.py`, no further configuration required. The app is not installed as hundreds of capitalization aliases. Store launch uses its marker directly.

## Free provider limits and privacy

Before the first network action the app asks whether you want to send explicit searches/coordinates to the public providers. This is a privacy choice, not an API signup. Never submit confidential addresses. Data providers can record your searches, route endpoints and IP address. Local favorites/cache stay in ~/.local/share/wayglint with private file permissions. No background location tracking, autocomplete or automatic refresh.

Public endpoints are best-effort donation/demo services. They can throttle, change or stop without notice; the app shows failures and never charges you or switches to a paid provider. Requests run single-threaded with at least two seconds spacing in one app process. This isn't an aggregate limiter across every installation; large-scale deployment needs separately hosted services. For an administrator-operated deployment, endpoints can be changed in providers.json without a code update. Ordinary users do not need that file.

- Photon permits reasonable project use, not guaranteed uptime: https://github.com/komoot/photon and https://github.com/komoot/photon/discussions/598
- OSM tiles: https://operations.osmfoundation.org/policies/tiles/ . Tiles cached for at least 7 days. No bulk downloads, offline prefetch or scraping.
- OSRM/FOSSGIS: https://routing.openstreetmap.de/about.html and https://www.fossgis.de/arbeitsgruppen/osm-server/nutzungsbedingungen/ . Explicit requests, no heavy usage.
- The public Nominatim service is NOT used: https://operations.osmfoundation.org/policies/nominatim/

Map/search/route data: OpenStreetMap contributors, ODbL. Tile graphics CC-BY-SA. https://www.openstreetmap.org/copyright . Routing: OSRM/FOSSGIS. Report map errors: https://www.openstreetmap.org/fixthemap . Attribution remains visible in the terminal.

## Offline regions

V1 is cached-view offline only. It does NOT download a region, provide offline address search or calculate new routes offline. Those need a permitted vector extract and local rendering/routing engine. Bulk OSM tile downloads are not an acceptable substitute. Geofabrik extracts are a possible future data source: https://download.geofabrik.de/ . No fake offline-download button.

## Tests and license

Unit tests, actual Photon search/OSM tile/OSRM route checks using public Berlin landmarks, live terminal visual/quit tests on Linux. No Raspberry Pi hardware test yet. Upstream services and road conditions aren't certified by a successful test. MIT app code, copyright 2026 Greenisus1. Provider data retains its own licenses.
