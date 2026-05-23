# Demo Script

Use this flow for a recruiter or project reviewer.

## One-Minute Story

This is a Southwest wildfire intelligence platform that began Arizona-first. It ingests active fire detections, renders them on a real map, clusters detections into incident areas, adds exposure and weather context, answers natural-language spatial questions, generates grounded incident reports, forecasts risk-grid trends, adds H3 spatial indexing, and includes a satellite before/after burn scar analysis demo.

## Local Run

Backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`.

## Docker Run

```bash
docker compose up --build
```

Open `http://127.0.0.1:8080`.

## Reviewer Flow

1. Open the app and confirm Arizona fire detections are visible.
2. Set the data source to `PostGIS` if the database has been loaded, or leave it on `Auto`.
3. Click a red fire point to inspect detection metadata.
4. Click a blue incident cluster to populate Incident Summary.
5. Review exposure, nearby places, weather, confidence, and FRP.
6. Click `Generate report` and confirm the AI report uses only structured facts.
7. Inspect the orange-red risk grid and click a grid cell to view score components.
8. Ask the Spatial Copilot: `Show wildfire risk near dense population zones in Arizona.`
9. Ask the Spatial Copilot: `Which counties are most vulnerable next week?`
10. Change the Region selector to `Southwest`, then to `California` or `Texas`, and confirm the map fits to the selected area.
11. Inspect the H3 Risk panel and explain why H3 indexing makes regional scaling easier than state-sized rectangular grids.
12. Run the What-If scenario with `+3°C`, drought `x1.2`, and wind `x1.1`; review changed top cells and caveats.
13. Switch Forecast between 24h, 48h, and 72h and review top projected changes.
14. Review Model Diagnostics and explain why proxy metrics are shown with caveats.
15. Review the Satellite Analysis panel and burn scar mask overlay.

## Resume Bullet

Built a full-stack GeoAI wildfire intelligence platform with React, MapLibre, FastAPI, PostGIS, H3 spatial indexing, NASA FIRMS ingestion, Census exposure analysis, NOAA weather context, grounded report generation, baseline spatial risk scoring, what-if simulations, and satellite burn scar visualization.

## Talking Points

- The project demonstrates geospatial pipelines, map rendering, spatial queries, API design, public-data integration, deterministic geospatial planning, and grounded AI reporting.
- The risk model is intentionally transparent first; the next step is MTBS/Sentinel-derived feature generation and model evaluation.
- The diagnostics panel shows proxy metrics now, while clearly separating demo diagnostics from operational validation.
- The copilot is deterministic in v1, which keeps the natural-language workflow testable and avoids hallucinated emergency claims.
- The LLM-style reports are grounded in computed incident summaries to avoid unsupported emergency claims.
- The H3 Southwest layer is a scaling foundation; non-Arizona state priors are deterministic demo fallbacks until full state loaders and historical labels are added.
