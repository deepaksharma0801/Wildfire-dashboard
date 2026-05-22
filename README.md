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
