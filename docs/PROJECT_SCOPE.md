# Wildfire GeoAI Intelligence Platform Scope

## Product Thesis

This project should feel like an intelligence system, not a notebook demo. A user opens a map, sees active wildfire detections and risk surfaces, clicks an area, and receives a grounded AI report explaining what is happening, what is exposed, and what actions or monitoring priorities make sense.

The strongest portfolio framing:

> A multimodal GeoAI platform combining satellite imagery, spatial databases, computer vision segmentation, temporal risk modeling, and LLM-based wildfire situation reports for real-world environmental decision support.

## First Vertical

Start with wildfire, not every disaster type at once.

Wildfire is ideal because it has clean public data, strong visual map demos, clear model targets, and obvious real-world value. Floods and storms can become later extensions once the core geospatial system is solid.

Initial geography:

- U.S. West/Southwest
- Arizona, California, New Mexico, Colorado, Nevada, Oregon, and Washington as likely early states
- County, census tract, or H3/quadkey grid as the main analysis units

## Target Users

- Emergency management analysts
- Utility or infrastructure risk teams
- Insurance and climate-risk analysts
- Civic-tech and public-sector data teams
- Recruiters evaluating applied AI, geospatial systems, and deployment ability

## MVP Outcome

The MVP should let a user:

1. View active wildfire detections on a real map.
2. Toggle risk and exposure layers.
3. Click a fire cluster, county, census tract, or grid cell.
4. See affected population, nearby roads, land cover, recent detections, and weather context.
5. Generate a concise AI situation report based on those computed metrics.
6. Use a time slider to inspect recent fire activity.

This MVP is already portfolio-worthy if it is deployed cleanly and documented well.

## Version Roadmap

### Phase 1: Map + Data Foundation

Goal: prove the geospatial system works end to end.

Build:

- FastAPI backend
- PostGIS database
- NASA FIRMS active fire ingestion
- County or census-tract boundaries
- Basic frontend map
- Fire detection layer
- Time slider for recent detections
- Click-to-query API

Primary demo:

- "Show me active fire detections in the Southwest over the last 7 days."

### Phase 2: Exposure Intelligence

Goal: convert map points into decision-support metrics.

Add:

- Population exposure from Census/ACS
- Road and place proximity from OpenStreetMap or public extracts
- Protected areas, critical facilities, or infrastructure if available
- Fire clustering by space and time
- Per-incident summary endpoint

Primary demo:

- "Click a fire cluster and see nearby communities, road access, estimated population exposure, and recent growth."

### Phase 3: Risk Scoring

Goal: create a meaningful predictive layer without overclaiming.

Add features:

- Recent fire detections
- Weather variables such as temperature, wind, humidity, and precipitation
- Vegetation indices such as NDVI where available
- Land cover or fuel proxy
- Terrain slope/elevation
- Historical fire occurrence

Model options:

- Start with a transparent baseline such as logistic regression, random forest, or gradient boosting.
- Later add temporal models if the baseline is strong and evaluation is honest.

Output:

- 24-72 hour grid-level wildfire risk score
- Calibrated classes such as low, moderate, high, and extreme
- Model evaluation with spatial and temporal holdout splits

Primary demo:

- "Show risk hotspots for the next 72 hours and explain which factors drive each hotspot."

### Phase 4: Satellite CV

Goal: add high-impact multimodal AI.

Add:

- Sentinel-2 imagery retrieval for selected incidents
- Before/after image comparison
- Burn scar or affected-area segmentation
- Raster-to-vector conversion for map overlay
- Damage extent summary

Model options:

- U-Net baseline
- SegFormer-style transformer segmentation
- Optional prompt-assisted segmentation workflow for demos

Training labels:

- Historical burn perimeters or burn scar products
- MTBS or similar public wildfire boundary datasets
- Curated incident chips for a smaller supervised dataset

Primary demo:

- "Compare pre-fire and post-fire satellite imagery, segment affected area, and overlay the burn scar on the map."

### Phase 5: LLM Situation Reports

Goal: use an LLM where it adds product value.

The LLM should not invent risk. It should summarize computed geospatial facts.

Inputs to report generation:

- Fire cluster geometry and time range
- Detection count and growth trend
- Nearby population and places
- Roads and access constraints
- Weather and wind context
- Historical fire context
- Model risk score
- Satellite-derived affected area when available

Outputs:

- Situation summary
- Exposure summary
- Likely operational concerns
- Monitoring recommendations
- Data caveats

Important rule:

- Reports must be grounded in structured metrics and cite the data layers used.

## Recommended Public Datasets

Core wildfire:

- NASA FIRMS active fire detections
- MTBS burn severity and historical fire boundaries
- NIFC or public wildfire perimeter datasets where accessible

Satellite and environmental:

- Sentinel-2 surface reflectance imagery
- Landsat imagery for historical analysis
- NLCD land cover
- LANDFIRE fuels or vegetation layers
- USGS elevation data

Weather and climate:

- NOAA weather observations or forecasts
- ERA5 or other reanalysis products for historical modeling
- PRISM climate normals if useful

Exposure:

- U.S. Census TIGER/Line boundaries
- ACS population and demographic variables
- OpenStreetMap roads, places, and infrastructure
- FEMA disaster declarations for historical context

## System Architecture

Data flow:

1. Ingestion jobs download or query source datasets.
2. Raw geospatial files are stored as source artifacts.
3. Processing jobs normalize projections, clean geometries, and create analysis features.
4. Vector data goes into PostGIS.
5. Raster data is stored as Cloud-Optimized GeoTIFFs or local GeoTIFFs during development.
6. ML jobs produce risk scores and segmentation masks.
7. FastAPI serves map layers, incident summaries, and report inputs.
8. React map visualizes detections, overlays, reports, and time controls.

Frontend views:

- Main incident map
- Layer control panel
- Time slider
- Incident detail drawer
- AI situation report panel
- Satellite before/after comparison
- Model diagnostics page for portfolio credibility

Backend endpoints:

- `GET /health`
- `GET /fires`
- `GET /fires/clusters`
- `GET /risk/grid`
- `GET /risk/{cell_id}`
- `GET /exposure/{area_id}`
- `POST /reports/incident`
- `GET /imagery/search`
- `GET /imagery/{incident_id}/before-after`

## ML Evaluation Plan

Risk model:

- Use temporal holdout to avoid training on the future.
- Use spatial holdout to test generalization to unseen regions.
- Report ROC-AUC, PR-AUC, calibration, precision at high-risk threshold, and false positive behavior.

Segmentation model:

- Use IoU, Dice/F1, precision, recall, and qualitative before/after examples.
- Include failure cases, especially smoke/clouds, terrain shadows, and mixed vegetation.

LLM reports:

- Evaluate factual grounding against structured inputs.
- Include a data-caveat section in every report.
- Keep generated text separate from computed metrics.

## Portfolio Deliverables

Must-have:

- Deployed live demo
- GitHub repo with clean README
- Architecture diagram
- Data pipeline documentation
- Model card
- Data card
- Demo video or GIF
- Screenshots of map, time slider, risk overlay, satellite comparison, and AI report

Resume bullet target:

> Built and deployed a multimodal GeoAI wildfire intelligence platform using PostGIS, FastAPI, React maps, NASA FIRMS, satellite imagery, computer vision segmentation, and LLM-grounded incident reports for environmental risk analysis.

## Practical Build Order

1. Scaffold repo with backend, frontend, data, and docs folders.
2. Build the FastAPI health endpoint and frontend map shell.
3. Ingest NASA FIRMS sample data into PostGIS.
4. Render active fire detections on the map.
5. Add time filtering and clustering.
6. Add Census boundaries and basic exposure metrics.
7. Generate structured incident summaries.
8. Add LLM report generation from structured summaries.
9. Add a baseline risk model.
10. Add satellite imagery search and before/after display.
11. Add segmentation model workflow.
12. Package and deploy.

## Scope Guardrails

Avoid these early:

- Trying to support every disaster type immediately
- Training a deep model before the map and data pipeline work
- Building a chatbot as the main interface
- Making unsupported emergency claims
- Depending on private or hard-to-access datasets
- Overbuilding cloud infrastructure before the MVP is useful

The project wins when it is practical, visual, grounded in real geospatial data, and honest about uncertainty.
