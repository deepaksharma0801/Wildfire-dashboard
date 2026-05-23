# Infrastructure

Local development usually runs two processes:

- FastAPI backend on `http://127.0.0.1:8000`
- Vite frontend on `http://127.0.0.1:5173`

The polished portfolio demo can run as containers:

```bash
docker compose up --build
```

Container services:

- Frontend/Nginx on `http://127.0.0.1:8080`
- FastAPI backend on `http://127.0.0.1:8000`
- PostGIS on `postgresql://wildfire:wildfire@127.0.0.1:5432/wildfire_geoai`

For database-only development:

```bash
docker compose up -d postgis
```
