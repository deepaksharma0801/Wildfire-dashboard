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
