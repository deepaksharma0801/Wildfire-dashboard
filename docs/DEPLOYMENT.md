# Deployment

## Local Development

Run backend and frontend separately when actively developing:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

```bash
cd frontend
npm run dev
```

## Docker Portfolio Demo

```bash
docker compose up --build
```

Services:

- Frontend: `http://127.0.0.1:8080`
- Backend: `http://127.0.0.1:8000`
- PostGIS: `127.0.0.1:5432`

The frontend container proxies `/api` and `/health` to the backend container.

## Loading Live Data

Run these locally before starting a polished demo:

```bash
cd backend
source .venv/bin/activate
FIRMS_MAP_KEY=your_key python scripts/ingest_firms.py --day-range 3
python scripts/ingest_counties.py
CENSUS_API_KEY=your_key python scripts/ingest_acs.py
python scripts/load_postgis.py
```

Only FIRMS requires a key for live fire ingestion. ACS has a sample fallback.

For Southwest refreshes, pass a region:

```bash
FIRMS_MAP_KEY=your_key python scripts/ingest_firms.py --region southwest --day-range 3
python scripts/ingest_counties.py --region southwest
CENSUS_API_KEY=your_key python scripts/ingest_acs.py --region southwest
```

## Scheduled ETL

Use the ETL runner for repeatable local refreshes:

```bash
cd backend
source .venv/bin/activate
python scripts/run_etl.py --mode sample
python scripts/run_etl.py --mode live
python scripts/run_etl.py --mode db-refresh
python scripts/run_etl.py --mode sample --region southwest
```

Modes:

- `sample`: verifies sample data and refreshes risk evaluation.
- `live`: runs FIRMS ingestion when `FIRMS_MAP_KEY` is set, then refreshes evaluation.
- `db-refresh`: refreshes boundaries/exposure when available and loads PostGIS.
- `--region`: selects `AZ`, `CA`, `NV`, `NM`, `TX`, `CO`, or `southwest`.

Logs are written to `data/processed/etl_runs/`.

## Cloud Notes

- Use managed Postgres with PostGIS enabled.
- Run FastAPI as a container service.
- Serve the frontend as static assets or via Nginx.
- Use object storage for large Sentinel/Landsat rasters and derived masks.
- Keep API keys in environment variables or a secret manager.
