# Data

This project keeps small demo data in version control and stores larger or downloaded artifacts locally.

- `sample/`: small, reproducible demo files used by Phase 1.
- `raw/`: downloaded source files, ignored by git.
- `processed/`: cleaned or derived files, ignored by git.

The Phase 1 wildfire points are FIRMS-like sample records for local development only.

Phase 2 adds live NASA FIRMS ingestion:

```bash
cd backend
source .venv/bin/activate
FIRMS_MAP_KEY=your_key python scripts/ingest_firms.py --day-range 3
```

That command writes raw CSV files to `data/raw/firms/` and normalized GeoJSON to `data/processed/firms_arizona_latest.geojson`.
