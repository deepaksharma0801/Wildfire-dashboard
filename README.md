# Wildfire GeoAI Intelligence Platform

A deployable geospatial AI portfolio project for wildfire monitoring, risk analysis, satellite-based damage mapping, and AI-generated situation reports.

The first build will focus on wildfire intelligence for the U.S. West/Southwest. The architecture should remain extensible to floods, storms, and other hazards later, but the MVP stays narrow enough to ship.

## Core Idea

Build a map-first decision-support system that combines:

- Real wildfire detections from NASA FIRMS
- Satellite imagery and burn-area analysis
- Weather, vegetation, terrain, population, and infrastructure features
- Spatial risk scoring and short-horizon forecasting
- LLM-generated incident reports grounded in geospatial metrics
- An interactive React map for exploration and demo

## Planned Stack

- Frontend: React, Mapbox GL JS or Deck.gl
- Backend: FastAPI
- Spatial storage: PostgreSQL/PostGIS
- Geospatial processing: GeoPandas, Rasterio, Shapely, PyProj
- ML/CV: PyTorch, segmentation model such as U-Net or SegFormer
- Pipelines: Python workers, scheduled ingestion jobs
- Deployment: Docker, cloud-hosted API, database, and static frontend

## Project Scope

See [docs/PROJECT_SCOPE.md](docs/PROJECT_SCOPE.md) for the detailed product, data, model, and implementation plan.

## Phase 1 Local Demo

The first executable slice uses a FastAPI backend, a React/Vite frontend, MapLibre GL, and a small FIRMS-like Arizona sample dataset.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at `http://127.0.0.1:5173`.

### Phase 1 Endpoints

- `GET /health`
- `GET /api/fires?start_date=&end_date=&bbox=&min_confidence=&data_source=`

## Phase 2 FIRMS Ingestion

Live fire detections use the [NASA FIRMS Area API](https://firms.modaps.eosdis.nasa.gov/api/area/). You need a free FIRMS `MAP_KEY`.

```bash
cd backend
source .venv/bin/activate
FIRMS_MAP_KEY=your_key python scripts/ingest_firms.py --day-range 3
```

The ingestion script:

- downloads Arizona-bounded FIRMS CSV data
- stores raw CSV under `data/raw/firms/`
- normalizes detections into GeoJSON at `data/processed/firms_arizona_latest.geojson`
- deduplicates detections by source, time, coordinates, satellite, and instrument

The API defaults to `data_source=auto`, which serves live FIRMS data if the processed file exists and falls back to the sample dataset otherwise.

Useful API examples:

```bash
curl "http://127.0.0.1:8000/api/fires?data_source=sample"
curl "http://127.0.0.1:8000/api/fires?data_source=live&min_confidence=60"
```

## Phase 3 PostGIS + Boundaries

Phase 3 adds PostgreSQL/PostGIS, database loading, and Arizona county boundaries.

Start PostGIS:

```bash
docker compose up -d postgis
```

Optional but recommended: download official Arizona county boundaries from Census TIGERweb:

```bash
cd backend
source .venv/bin/activate
python scripts/ingest_counties.py
```

Load fires and counties into PostGIS:

```bash
cd backend
source .venv/bin/activate
python scripts/load_postgis.py
```

Optional: download official ACS county exposure metrics before loading PostGIS:

```bash
cd backend
source .venv/bin/activate
CENSUS_API_KEY=your_key python scripts/ingest_acs.py
python scripts/load_postgis.py
```

Serve database-backed layers:

```bash
FIRE_DATA_SOURCE=db BOUNDARY_DATA_SOURCE=db uvicorn app.main:app --reload
```

Or choose `PostGIS` in the app's data-source dropdown.

Useful API examples:

```bash
curl "http://127.0.0.1:8000/api/fires?data_source=db"
curl "http://127.0.0.1:8000/api/counties?data_source=db"
```

## Phase 4 Exposure Intelligence

Phase 4 adds incident clustering and exposure summaries.

New endpoints:

- `GET /api/fires/clusters?start_date=&end_date=&bbox=&min_confidence=&radius_km=&data_source=`
- `GET /api/incidents/{incident_id}/summary?radius_km=&data_source=`

The incident summary includes:

- detection count and time span
- average confidence and peak FRP
- area-weighted county population and household exposure
- nearest Arizona places
- data caveats for FIRMS and exposure precision

In the app, click a blue incident cluster to populate the Incident Summary panel.

## Phase 5 Weather Context

Phase 5 adds NOAA/NWS forecast context to incident summaries. The NWS API does not require an API key, but it does require a User-Agent. You can optionally set one:

```bash
export NWS_USER_AGENT="wildfire-geoai/0.1 (you@example.com)"
```

New endpoint:

- `GET /api/weather/point?latitude=&longitude=`

Incident summaries now include:

- current forecast period
- temperature
- wind speed and direction
- short forecast
- 12-hour max temperature, wind, and precipitation probability
- operational weather flags

Weather responses are cached under `data/cache/weather/` for 30 minutes.

## Phase 6 Grounded Incident Reports

Phase 6 adds a report endpoint that generates structured incident reports from computed metrics only. The first implementation uses a deterministic template mode, so no LLM API key is required.

New endpoint:

- `POST /api/reports/incident`

Request body:

```json
{
  "mode": "template",
  "incident_summary": {}
}
```

The report includes:

- situation
- exposure
- weather concerns
- monitoring priorities
- data caveats
- grounding metadata showing which structured fields were used

In the app, click a blue incident cluster, wait for the Incident Summary, then click **Generate report**.

## Phase 7 Baseline Risk Grid

Phase 7 adds the first 24-72 hour risk surface. It is a transparent baseline layer for portfolio/demo use, not an operational wildfire forecast.

New endpoint:

- `GET /api/risk/grid?start_date=&end_date=&bbox=&min_confidence=&horizon_hours=&cell_size_deg=&data_source=`

The current score combines:

- recent FIRMS detection proximity and confidence
- fire radiative power intensity proxy
- sample Arizona historical fire priors
- nearby population-place exposure proxy

Useful API example:

```bash
curl "http://127.0.0.1:8000/api/risk/grid?data_source=sample&horizon_hours=72"
```

In the app, the risk grid appears as a yellow-orange-red overlay. Click a grid cell to inspect its score, recent activity, historical prior, intensity, and nearby detection count.

No new API keys are required for Phase 7. Later iterations should replace the sample historical priors with MTBS-derived features and add weather, fuel, terrain, and evaluated train/test splits.

## Phase 8 Satellite Burn Scar Analysis

Phase 8 adds the first satellite/CV-style workflow. The current implementation uses local Sentinel-2-style sample imagery so the demo works without Copernicus credentials or raster downloads.

New endpoints:

- `GET /api/imagery/search`
- `GET /api/imagery/{incident_id}/before-after`

Useful API examples:

```bash
curl "http://127.0.0.1:8000/api/imagery/search"
curl "http://127.0.0.1:8000/api/imagery/sample/before-after"
```

The app now includes a **Satellite Analysis** panel with:

- before/after false-color sample imagery
- burn scar mask overlay on the map
- burn area, mean dNBR, cloud cover, and severity class
- severity mix bars

No new API keys are required for this demo slice. The production version should connect this to Copernicus Sentinel-2 scenes, compute NDVI/NBR/dNBR from raster bands, and replace the sample mask with MTBS-derived or model-predicted burn polygons.
