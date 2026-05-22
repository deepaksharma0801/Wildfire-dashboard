# Infrastructure

Phase 1 runs locally with two processes:

- FastAPI backend on `http://127.0.0.1:8000`
- Vite frontend on `http://127.0.0.1:5173`

Phase 3 adds PostGIS:

```bash
docker compose up -d postgis
```

The database is available at `postgresql://wildfire:wildfire@127.0.0.1:5432/wildfire_geoai`.
