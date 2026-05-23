# Data Card

## Project Scope

The current project is an Arizona-first wildfire intelligence demo. It combines real public-data integrations with local sample data so the application remains runnable without paid services.

## Datasets

| Dataset | Current Use | Status | Key |
| --- | --- | --- | --- |
| NASA FIRMS active fire detections | Fire points, clusters, risk features | Live ingestion supported | `FIRMS_MAP_KEY` |
| Census TIGER/Line counties | Arizona county boundaries | Ingestion supported, sample fallback | None |
| ACS 5-year county fields | Population and household exposure | Optional ingestion, sample fallback | `CENSUS_API_KEY` optional |
| NOAA/NWS API | Incident weather context | Live request + local cache | None |
| Historical fire priors | Baseline risk proxy | Sample portfolio data | None |
| Sentinel-2 style imagery | Before/after burn scar demo | Local sample assets | None |

## Files

- `data/sample/firms_arizona_sample.geojson`: small FIRMS-like point sample.
- `data/processed/firms_arizona_latest.geojson`: latest normalized FIRMS output after ingestion.
- `data/sample/arizona_counties_sample.geojson`: simplified counties.
- `data/processed/arizona_counties.geojson`: official TIGERweb county download when available.
- `data/sample/arizona_county_exposure_sample.json`: local exposure fallback.
- `data/sample/arizona_places_sample.json`: nearby-place fallback.
- `data/sample/arizona_historical_fire_priors.json`: transparent risk-prior sample.
- `data/sample/imagery/`: local before/after imagery and burn scar mask.

## Known Limitations

- FIRMS detections are hotspots, not official incident boundaries.
- Exposure is approximate and depends on county-level sample data unless ACS ingestion is run.
- The risk grid is a baseline screening layer, not an operational forecast.
- The current satellite imagery is a local demo asset, not downloaded Sentinel-2 bands.
- Weather values depend on NWS API availability and forecast-grid coverage.

## Data Ethics And Safety

This app should not be used for evacuation, suppression, emergency response, or public warning decisions. It is a portfolio-grade decision-support prototype that demonstrates data integration, geospatial analysis, and grounded reporting.
