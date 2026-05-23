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

## Implemented Stack

- Frontend: React, Vite, MapLibre GL, Nginx for container serving
- Backend: FastAPI
- Spatial storage: PostgreSQL/PostGIS
- Geospatial processing: GeoJSON, PostGIS spatial queries, Python scoring utilities
- AI layer: grounded report generation from structured incident summaries
- CV/imagery layer: Sentinel-2-style before/after burn scar demo
- Deployment: Docker Compose with frontend, backend, and PostGIS services

## Project Docs

- [Project scope](docs/PROJECT_SCOPE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data card](docs/DATA_CARD.md)
- [Model card](docs/MODEL_CARD.md)
- [Demo script](docs/DEMO_SCRIPT.md)
- [Deployment guide](docs/DEPLOYMENT.md)

## Quick Start

Run the full portfolio demo with Docker:

```bash
docker compose up --build
```

Open `http://127.0.0.1:8080`.

For development, run the backend and frontend separately:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Demo Flow

1. View Arizona fire detections on the map.
2. Click a fire point to inspect raw FIRMS-style metadata.
3. Click a blue incident cluster to load exposure and weather context.
4. Generate a grounded AI-style incident report.
5. Click the risk grid to inspect model score components.
6. Review Model Diagnostics to see proxy evaluation metrics.
7. Ask the Spatial Copilot a supported geospatial question.
8. Switch the forecast horizon between 24h, 48h, and 72h.
9. Review the Satellite Analysis panel and burn scar mask.

## Resume Bullet

Built a full-stack GeoAI wildfire intelligence platform with React, MapLibre, FastAPI, PostGIS, NASA FIRMS ingestion, Census exposure analysis, NOAA weather context, grounded report generation, baseline spatial risk scoring, and satellite burn scar visualization.

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

## Phase 10 Risk Model Diagnostics

Phase 10 adds a proxy evaluation layer for the baseline risk model. This makes the project more credible by exposing metrics, caveats, and feature weights instead of only showing a risk map.

New endpoint:

- `GET /api/risk/evaluation`

Regenerate the evaluation artifact:

```bash
cd backend
source .venv/bin/activate
python scripts/evaluate_risk_baseline.py
```

The script writes `models/risk_baseline_evaluation.json`.

Current proxy metrics:

- ROC AUC: 0.975
- Precision: 0.2
- Recall: 1.0
- F1: 0.333

These are proxy diagnostics against sample FIRMS-proximity labels, not operational validation. The next true modeling step is to use MTBS burn perimeters as labels and evaluate with spatial/temporal holdouts.

## Phase 11 Spatial Copilot + Forecast + ETL

Phase 11 adds the first agentic spatial intelligence workflow without requiring an LLM key. The copilot uses a deterministic planner so demos are reliable and answers stay grounded in computed metrics.

New endpoints:

- `POST /api/copilot/query`
- `GET /api/forecast/risk-grid?horizon_hours=24|48|72&data_source=&bbox=&min_confidence=`

Copilot example:

```bash
curl -X POST "http://127.0.0.1:8000/api/copilot/query" \
  -H "Content-Type: application/json" \
  -d '{"query":"Show wildfire risk near dense population zones in Arizona.","data_source":"sample","min_confidence":50}'
```

Forecast example:

```bash
curl "http://127.0.0.1:8000/api/forecast/risk-grid?data_source=sample&horizon_hours=72"
```

Scheduled ETL:

```bash
cd backend
source .venv/bin/activate
python scripts/run_etl.py --mode sample
python scripts/run_etl.py --mode live
python scripts/run_etl.py --mode db-refresh
```

ETL logs are written to `data/processed/etl_runs/`. Optional keys are skipped with explicit log entries when missing.

## Phase 12 Southwest + H3 Scaling

Phase 12 scales the app from Arizona-first to a Southwest spatial intelligence foundation while keeping wildfire as the core hazard.

New endpoints:

- `GET /api/regions`
- `GET /api/risk/h3-grid?region=AZ|CA|NV|NM|TX|CO|southwest&h3_resolution=4|5|6&data_source=`
- `POST /api/simulations/risk-scenario`

H3 risk example:

```bash
curl "http://127.0.0.1:8000/api/risk/h3-grid?region=southwest&h3_resolution=5&data_source=sample"
```

What-if example:

```bash
curl -X POST "http://127.0.0.1:8000/api/simulations/risk-scenario" \
  -H "Content-Type: application/json" \
  -d '{"region":"southwest","h3_resolution":5,"horizon_hours":72,"temperature_delta_c":3,"drought_multiplier":1.2,"wind_multiplier":1.1,"data_source":"sample"}'
```

Regional ETL:

```bash
cd backend
source .venv/bin/activate
python scripts/run_etl.py --mode sample --region southwest
python scripts/run_etl.py --mode live --region southwest
python scripts/run_etl.py --mode db-refresh --region southwest
```

The H3 layer uses real H3 cell IDs and geometries with deterministic regional priors/exposure fallbacks for non-Arizona states until expanded live loaders are populated.
