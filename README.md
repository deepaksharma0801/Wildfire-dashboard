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
- `GET /api/fires?start_date=&end_date=&bbox=&min_confidence=`
