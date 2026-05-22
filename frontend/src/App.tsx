import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { GeoJSONSource, MapLayerMouseEvent } from "maplibre-gl";
import type { FeatureCollection, Polygon } from "geojson";
import {
  CalendarDays,
  DatabaseZap,
  Flame,
  Layers,
  RotateCcw,
  Satellite,
  SlidersHorizontal
} from "lucide-react";
import {
  CountyCollection,
  CountyFeature,
  CountyProperties,
  FireClusterCollection,
  FireClusterFeature,
  FireClusterProperties,
  FireCollection,
  FireFeature,
  FireProperties,
  IncidentReport,
  IncidentSummary,
  RiskCellFeature,
  RiskCellProperties,
  RiskGridCollection
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const ARIZONA_BBOX = "-115.1,31.2,-108.8,37.1";
const arizonaBounds: FeatureCollection<Polygon> = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-115.1, 31.2],
            [-108.8, 31.2],
            [-108.8, 37.1],
            [-115.1, 37.1],
            [-115.1, 31.2]
          ]
        ]
      }
    }
  ]
};

const initialFilters = {
  startDate: "",
  endDate: "",
  minConfidence: 50,
  dataSource: "auto"
};

const emptyCollection: FireCollection = {
  type: "FeatureCollection",
  features: []
};

const emptyCountyCollection: CountyCollection = {
  type: "FeatureCollection",
  features: []
};

const emptyClusterCollection: FireClusterCollection = {
  type: "FeatureCollection",
  features: []
};

const emptyRiskGrid: RiskGridCollection = {
  type: "FeatureCollection",
  features: []
};

function countyName(properties: CountyProperties) {
  return properties.name ?? properties.NAME ?? "Selected county";
}

function formatNumber(value: number | undefined) {
  return typeof value === "number" ? value.toLocaleString() : "n/a";
}

function App() {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [fires, setFires] = useState<FireCollection>(emptyCollection);
  const [counties, setCounties] = useState<CountyCollection>(emptyCountyCollection);
  const [clusters, setClusters] = useState<FireClusterCollection>(emptyClusterCollection);
  const [riskGrid, setRiskGrid] = useState<RiskGridCollection>(emptyRiskGrid);
  const [selectedFire, setSelectedFire] = useState<FireProperties | null>(null);
  const [selectedCounty, setSelectedCounty] = useState<CountyProperties | null>(null);
  const [selectedCluster, setSelectedCluster] = useState<FireClusterProperties | null>(null);
  const [selectedRiskCell, setSelectedRiskCell] = useState<RiskCellProperties | null>(null);
  const [incidentSummary, setIncidentSummary] = useState<IncidentSummary | null>(null);
  const [incidentReport, setIncidentReport] = useState<IncidentReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [filters, setFilters] = useState(initialFilters);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const stats = useMemo(() => {
    const count = fires.features.length;
    const confidenceTotal = fires.features.reduce(
      (total, feature) => total + feature.properties.confidence,
      0
    );
    const peakFrp = fires.features.reduce(
      (max, feature) => Math.max(max, feature.properties.frp_mw),
      0
    );
    const peakRisk = riskGrid.features.reduce(
      (max, feature) => Math.max(max, feature.properties.risk_score),
      0
    );

    return {
      count,
      averageConfidence: count ? Math.round(confidenceTotal / count) : 0,
      peakFrp: peakFrp.toFixed(1),
      peakRisk: peakRisk.toFixed(0)
    };
  }, [fires, riskGrid]);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
      center: [-111.8, 34.3],
      zoom: 5.7,
      minZoom: 4,
      attributionControl: false
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchFires() {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({
        bbox: ARIZONA_BBOX,
        min_confidence: String(filters.minConfidence),
        data_source: filters.dataSource
      });

      if (filters.startDate) {
        params.set("start_date", filters.startDate);
      }
      if (filters.endDate) {
        params.set("end_date", filters.endDate);
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/fires?${params}`, {
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`Fire API returned ${response.status}`);
        }

        const payload = (await response.json()) as FireCollection;
          setFires(payload);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setError((requestError as Error).message);
        }
      } finally {
        setLoading(false);
      }
    }

    fetchFires();

    return () => controller.abort();
  }, [filters]);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchClusters() {
      const params = new URLSearchParams({
        bbox: ARIZONA_BBOX,
        min_confidence: String(filters.minConfidence),
        data_source: filters.dataSource,
        radius_km: "25"
      });

      if (filters.startDate) {
        params.set("start_date", filters.startDate);
      }
      if (filters.endDate) {
        params.set("end_date", filters.endDate);
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/fires/clusters?${params}`, {
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`Cluster API returned ${response.status}`);
        }

        const payload = (await response.json()) as FireClusterCollection;
        setClusters(payload);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setClusters(emptyClusterCollection);
        }
      }
    }

    fetchClusters();

    return () => controller.abort();
  }, [filters]);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchRiskGrid() {
      const params = new URLSearchParams({
        bbox: ARIZONA_BBOX,
        min_confidence: String(filters.minConfidence),
        data_source: filters.dataSource,
        horizon_hours: "72",
        cell_size_deg: "0.5"
      });

      if (filters.startDate) {
        params.set("start_date", filters.startDate);
      }
      if (filters.endDate) {
        params.set("end_date", filters.endDate);
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/risk/grid?${params}`, {
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`Risk API returned ${response.status}`);
        }

        setRiskGrid((await response.json()) as RiskGridCollection);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setRiskGrid(emptyRiskGrid);
          setSelectedRiskCell(null);
        }
      }
    }

    fetchRiskGrid();

    return () => controller.abort();
  }, [filters]);

  useEffect(() => {
    const controller = new AbortController();
    const countyDataSource = filters.dataSource === "db" ? "db" : "auto";

    async function fetchCounties() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/counties?data_source=${countyDataSource}`, {
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`County API returned ${response.status}`);
        }

        const payload = (await response.json()) as CountyCollection;
        setCounties(payload);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setCounties(emptyCountyCollection);
        }
      }
    }

    fetchCounties();

    return () => controller.abort();
  }, [filters.dataSource]);

  useEffect(() => {
    if (selectedFire && !fires.features.some((feature) => feature.properties.id === selectedFire.id)) {
        setSelectedFire(null);
      }
  }, [fires, selectedFire]);

  useEffect(() => {
    if (
      selectedRiskCell &&
      !riskGrid.features.some((feature) => feature.properties.id === selectedRiskCell.id)
    ) {
      setSelectedRiskCell(null);
    }
  }, [riskGrid, selectedRiskCell]);

  useEffect(() => {
    if (
      selectedCluster &&
      !clusters.features.some((feature) => feature.properties.id === selectedCluster.id)
    ) {
      setSelectedCluster(null);
      setIncidentSummary(null);
      setIncidentReport(null);
    }
  }, [clusters, selectedCluster]);

  useEffect(() => {
    const controller = new AbortController();
    if (!selectedCluster) {
      return () => controller.abort();
    }
    const cluster = selectedCluster;

    async function fetchIncidentSummary() {
      const params = new URLSearchParams({
        bbox: ARIZONA_BBOX,
        min_confidence: String(filters.minConfidence),
        data_source: filters.dataSource,
        radius_km: String(cluster.radius_km ?? 25)
      });

      if (filters.startDate) {
        params.set("start_date", filters.startDate);
      }
      if (filters.endDate) {
        params.set("end_date", filters.endDate);
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/incidents/${cluster.id}/summary?${params}`,
          { signal: controller.signal }
        );

        if (!response.ok) {
          throw new Error(`Incident API returned ${response.status}`);
        }

        setIncidentSummary((await response.json()) as IncidentSummary);
        setIncidentReport(null);
        setReportError(null);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setIncidentSummary(null);
          setIncidentReport(null);
        }
      }
    }

    fetchIncidentSummary();

    return () => controller.abort();
  }, [filters, selectedCluster]);

  async function generateIncidentReport() {
    if (!incidentSummary) {
      return;
    }

    setReportLoading(true);
    setReportError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/reports/incident`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ incident_summary: incidentSummary, mode: "template" })
      });

      if (!response.ok) {
        throw new Error(`Report API returned ${response.status}`);
      }

      setIncidentReport((await response.json()) as IncidentReport);
    } catch (requestError) {
      setReportError((requestError as Error).message);
    } finally {
      setReportLoading(false);
    }
  }

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncRiskLayer = () => {
      const existingSource = map.getSource("risk-grid") as GeoJSONSource | undefined;

      if (existingSource) {
        existingSource.setData(riskGrid);
        return;
      }

      map.addSource("risk-grid", {
        type: "geojson",
        data: riskGrid
      });

      map.addLayer({
        id: "risk-grid-fill",
        type: "fill",
        source: "risk-grid",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "risk_score"],
            0,
            "#f1f5f9",
            30,
            "#facc15",
            55,
            "#f97316",
            75,
            "#dc2626"
          ],
          "fill-opacity": [
            "interpolate",
            ["linear"],
            ["get", "risk_score"],
            0,
            0.04,
            30,
            0.18,
            75,
            0.34
          ]
        }
      }, map.getLayer("county-fill") ? "county-fill" : undefined);

      map.addLayer({
        id: "risk-grid-line",
        type: "line",
        source: "risk-grid",
        paint: {
          "line-color": "#7c2d12",
          "line-width": 0.4,
          "line-opacity": 0.2
        }
      }, map.getLayer("county-fill") ? "county-fill" : undefined);

      map.on("click", "risk-grid-fill", (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0] as unknown as RiskCellFeature | undefined;
        if (!feature) {
          return;
        }
        setSelectedRiskCell(feature.properties);
      });

      map.on("mouseenter", "risk-grid-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "risk-grid-fill", () => {
        map.getCanvas().style.cursor = "";
      });
    };

    if (map.isStyleLoaded()) {
      syncRiskLayer();
    } else {
      map.once("load", syncRiskLayer);
    }
  }, [riskGrid]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncClusterLayer = () => {
      const existingSource = map.getSource("clusters") as GeoJSONSource | undefined;

      if (existingSource) {
        existingSource.setData(clusters);
        return;
      }

      map.addSource("clusters", {
        type: "geojson",
        data: clusters
      });

      map.addLayer({
        id: "cluster-rings",
        type: "circle",
        source: "clusters",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "detection_count"], 1, 16, 8, 34],
          "circle-color": "#2563eb",
          "circle-opacity": 0.13,
          "circle-stroke-color": "#1d4ed8",
          "circle-stroke-opacity": 0.45,
          "circle-stroke-width": 1.2
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);

      map.addLayer({
        id: "cluster-centers",
        type: "circle",
        source: "clusters",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "detection_count"], 1, 5, 8, 11],
          "circle-color": "#1d4ed8",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
          "circle-opacity": 0.88
        }
      });

      map.on("click", "cluster-centers", (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0] as unknown as FireClusterFeature | undefined;
        if (!feature) {
          return;
        }

                setSelectedCluster(feature.properties);
                setIncidentSummary(null);
                setIncidentReport(null);
                setReportError(null);
                map.flyTo({
          center: feature.geometry.coordinates,
          zoom: Math.max(map.getZoom(), 7),
          speed: 0.8
        });
      });

      map.on("mouseenter", "cluster-centers", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "cluster-centers", () => {
        map.getCanvas().style.cursor = "";
      });
    };

    if (map.isStyleLoaded()) {
      syncClusterLayer();
    } else {
      map.once("load", syncClusterLayer);
    }
  }, [clusters]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncCountyLayer = () => {
      const existingSource = map.getSource("counties") as GeoJSONSource | undefined;

      if (existingSource) {
        existingSource.setData(counties);
        return;
      }

      map.addSource("counties", {
        type: "geojson",
        data: counties
      });

      map.addLayer({
        id: "county-fill",
        type: "fill",
        source: "counties",
        paint: {
          "fill-color": "#0891b2",
          "fill-opacity": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            0.18,
            0.07
          ]
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);

      map.addLayer({
        id: "county-line",
        type: "line",
        source: "counties",
        paint: {
          "line-color": "#0e7490",
          "line-width": 1.5,
          "line-opacity": 0.8
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);

      map.on("click", "county-fill", (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0] as unknown as CountyFeature | undefined;
        if (!feature) {
          return;
        }
        setSelectedCounty(feature.properties);
      });

      map.on("mouseenter", "county-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "county-fill", () => {
        map.getCanvas().style.cursor = "";
      });
    };

    if (map.isStyleLoaded()) {
      syncCountyLayer();
    } else {
      map.once("load", syncCountyLayer);
    }
  }, [counties]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncFireLayer = () => {
      if (!map.getSource("arizona-bounds")) {
        map.addSource("arizona-bounds", {
          type: "geojson",
          data: arizonaBounds
        });

        map.addLayer({
          id: "arizona-bounds-fill",
          type: "fill",
          source: "arizona-bounds",
          paint: {
            "fill-color": "#0891b2",
            "fill-opacity": 0.04
          }
        });

        map.addLayer({
          id: "arizona-bounds-line",
          type: "line",
          source: "arizona-bounds",
          paint: {
            "line-color": "#0891b2",
            "line-width": 2,
            "line-dasharray": [2, 2]
          }
        });
      }

      const existingSource = map.getSource("fires") as GeoJSONSource | undefined;

      if (existingSource) {
        existingSource.setData(fires);
        return;
      }

      map.addSource("fires", {
        type: "geojson",
        data: fires
      });

      map.addLayer({
        id: "fire-halos",
        type: "circle",
        source: "fires",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "frp_mw"], 0, 10, 25, 28],
          "circle-color": "#f97316",
          "circle-opacity": 0.16,
          "circle-blur": 0.25
        }
      });

      map.addLayer({
        id: "fire-points",
        type: "circle",
        source: "fires",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "confidence"], 50, 5, 95, 9],
          "circle-color": [
            "interpolate",
            ["linear"],
            ["get", "confidence"],
            50,
            "#f59e0b",
            75,
            "#ef4444",
            95,
            "#7f1d1d"
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
          "circle-opacity": 0.94
        }
      });

      map.on("click", "fire-points", (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0] as unknown as FireFeature | undefined;
        if (!feature) {
          return;
        }

        setSelectedFire(feature.properties);
        map.flyTo({
          center: feature.geometry.coordinates,
          zoom: Math.max(map.getZoom(), 7),
          speed: 0.8
        });
      });

      map.on("mouseenter", "fire-points", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "fire-points", () => {
        map.getCanvas().style.cursor = "";
      });
    };

    if (map.isStyleLoaded()) {
      syncFireLayer();
    } else {
      map.once("load", syncFireLayer);
    }
  }, [fires]);

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Wildfire intelligence controls">
        <header className="brand-block">
          <div className="brand-mark">
            <Flame size={22} aria-hidden="true" />
          </div>
          <div>
            <p className="eyebrow">Arizona first</p>
            <h1>Wildfire GeoAI</h1>
          </div>
        </header>

        <section className="metric-grid" aria-label="Detection metrics">
          <div className="metric-tile">
            <span>Detections</span>
            <strong>{stats.count}</strong>
          </div>
          <div className="metric-tile">
            <span>Avg confidence</span>
            <strong>{stats.averageConfidence}%</strong>
          </div>
          <div className="metric-tile">
            <span>Peak FRP</span>
            <strong>{stats.peakFrp}</strong>
          </div>
          <div className="metric-tile">
            <span>Clusters</span>
            <strong>{clusters.features.length}</strong>
          </div>
          <div className="metric-tile">
            <span>Peak risk</span>
            <strong>{stats.peakRisk}</strong>
          </div>
        </section>

        <section className="control-panel" aria-label="Fire filters">
          <div className="section-heading">
            <CalendarDays size={18} aria-hidden="true" />
            <h2>Time Window</h2>
          </div>

          <label>
            <span>Start date</span>
            <input
              type="date"
              value={filters.startDate}
              onChange={(event) =>
                setFilters((current) => ({ ...current, startDate: event.target.value }))
              }
            />
          </label>

          <label>
            <span>End date</span>
            <input
              type="date"
              value={filters.endDate}
              onChange={(event) =>
                setFilters((current) => ({ ...current, endDate: event.target.value }))
              }
            />
          </label>

          <div className="range-row">
            <div>
              <span>Minimum confidence</span>
              <strong>{filters.minConfidence}%</strong>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={filters.minConfidence}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  minConfidence: Number(event.target.value)
                }))
              }
            />
          </div>

          <label>
            <span>Data source</span>
            <select
              value={filters.dataSource}
              onChange={(event) =>
                setFilters((current) => ({ ...current, dataSource: event.target.value }))
              }
            >
              <option value="auto">Auto</option>
              <option value="db">PostGIS</option>
              <option value="sample">Sample</option>
              <option value="live">Live FIRMS</option>
            </select>
          </label>

          <button className="icon-button" type="button" onClick={() => setFilters(initialFilters)}>
            <RotateCcw size={16} aria-hidden="true" />
            Reset filters
          </button>
        </section>

        <section className="layer-panel" aria-label="Active layers">
          <div className="section-heading">
            <DatabaseZap size={18} aria-hidden="true" />
            <h2>Data Feed</h2>
          </div>
          <div className="source-card">
            <span>Resolved source</span>
            <strong>{fires.metadata?.source ?? "pending"}</strong>
          </div>
          <div className="source-card">
            <span>County source</span>
            <strong>{counties.metadata?.source ?? "pending"}</strong>
          </div>
          <div className="source-card">
            <span>Cluster method</span>
            <strong>{clusters.metadata?.cluster_method ?? "pending"}</strong>
          </div>
          <div className="source-card">
            <span>Risk model</span>
            <strong>{riskGrid.metadata?.model_version ?? "pending"}</strong>
          </div>
        </section>

        <section className="layer-panel" aria-label="Active layers">
          <div className="section-heading">
            <Layers size={18} aria-hidden="true" />
            <h2>Layers</h2>
          </div>
          <div className="layer-row active">
            <span className="layer-dot fire" />
            <span>Fire detections</span>
          </div>
          <div className="layer-row">
            <span className="layer-dot cluster" />
            <span>Incident clusters</span>
          </div>
          <div className="layer-row">
            <span className="layer-dot boundary" />
            <span>Arizona counties</span>
          </div>
          <div className="layer-row">
            <span className="layer-dot risk" />
            <span>Risk grid</span>
          </div>
        </section>

        <section className="detail-panel" aria-label="Risk grid detail">
          <div className="section-heading">
            <SlidersHorizontal size={18} aria-hidden="true" />
            <h2>Risk Layer</h2>
          </div>
          {selectedRiskCell ? (
            <div className="detail-stack">
              <div>
                <p className="eyebrow">{selectedRiskCell.model_version}</p>
                <h3>{selectedRiskCell.risk_class} risk</h3>
              </div>
              <dl>
                <div>
                  <dt>Score</dt>
                  <dd>{selectedRiskCell.risk_score}/100</dd>
                </div>
                <div>
                  <dt>Recent activity</dt>
                  <dd>{Math.round(selectedRiskCell.recent_activity * 100)}%</dd>
                </div>
                <div>
                  <dt>Historical prior</dt>
                  <dd>{Math.round(selectedRiskCell.historical_prior * 100)}%</dd>
                </div>
                <div>
                  <dt>Intensity</dt>
                  <dd>{Math.round(selectedRiskCell.intensity * 100)}%</dd>
                </div>
                <div>
                  <dt>Nearby detections</dt>
                  <dd>{selectedRiskCell.nearby_detection_count}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <div className="risk-legend">
              <p className="empty-copy">Click a grid cell to inspect the baseline score</p>
              <div><span className="legend-swatch low" /> Low</div>
              <div><span className="legend-swatch moderate" /> Moderate</div>
              <div><span className="legend-swatch high" /> High</div>
              <div><span className="legend-swatch extreme" /> Extreme</div>
            </div>
          )}
        </section>

        <section className="detail-panel" aria-label="Incident summary">
          <div className="section-heading">
            <Flame size={18} aria-hidden="true" />
            <h2>Incident Summary</h2>
          </div>
          {selectedCluster ? (
            <div className="detail-stack">
              <div>
                <p className="eyebrow">{selectedCluster.source}</p>
                <h3>{selectedCluster.detection_count} detections</h3>
              </div>
              <dl>
                <div>
                  <dt>Time span</dt>
                  <dd>{selectedCluster.time_start.slice(0, 10)} to {selectedCluster.time_end.slice(0, 10)}</dd>
                </div>
                <div>
                  <dt>Avg confidence</dt>
                  <dd>{selectedCluster.avg_confidence}%</dd>
                </div>
                <div>
                  <dt>Max FRP</dt>
                  <dd>{selectedCluster.max_frp_mw} MW</dd>
                </div>
                <div>
                  <dt>Est. population</dt>
                  <dd>{formatNumber(incidentSummary?.estimated_population_exposed)}</dd>
                </div>
                <div>
                  <dt>Est. households</dt>
                  <dd>{formatNumber(incidentSummary?.estimated_households_exposed)}</dd>
                </div>
              </dl>
              {incidentSummary?.weather ? (
                <div className="weather-card">
                  <span>Weather context</span>
                  {incidentSummary.weather.unavailable ? (
                    <p>{incidentSummary.weather.message ?? "Weather unavailable"}</p>
                  ) : (
                    <>
                      <strong>
                        {incidentSummary.weather.current_period?.temperature ?? "n/a"}
                        {incidentSummary.weather.current_period?.temperature_unit ?? ""} ·{" "}
                        {incidentSummary.weather.current_period?.wind_speed ?? "wind n/a"}{" "}
                        {incidentSummary.weather.current_period?.wind_direction ?? ""}
                      </strong>
                      <p>{incidentSummary.weather.current_period?.short_forecast ?? "Forecast pending"}</p>
                      <ul>
                        {(incidentSummary.weather.operational_flags ?? []).map((flag) => (
                          <li key={flag}>{flag}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              ) : null}
              {incidentSummary?.nearby_places?.length ? (
                <div className="place-list">
                  <span>Nearby places</span>
                  {incidentSummary.nearby_places.slice(0, 3).map((place) => (
                    <div key={place.id} className="place-row">
                      <strong>{place.name}</strong>
                      <em>{place.distance_km} km</em>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="empty-copy">Loading exposure summary</p>
              )}
              <button
                className="icon-button"
                type="button"
                onClick={generateIncidentReport}
                disabled={!incidentSummary || reportLoading}
              >
                <SlidersHorizontal size={16} aria-hidden="true" />
                {reportLoading ? "Generating report" : "Generate report"}
              </button>
            </div>
          ) : (
            <p className="empty-copy">Click a blue incident cluster</p>
          )}
        </section>

        <section className="detail-panel" aria-label="AI incident report">
          <div className="section-heading">
            <Satellite size={18} aria-hidden="true" />
            <h2>AI Report</h2>
          </div>
          {incidentReport ? (
            <div className="report-stack">
              <p className="eyebrow">{incidentReport.mode} · grounded</p>
              {Object.entries(incidentReport.sections).map(([title, body]) => (
                <article key={title} className="report-section">
                  <h3>{title.replace("_", " ")}</h3>
                  <p>{body}</p>
                </article>
              ))}
              <div className="source-card">
                <span>Grounding policy</span>
                <strong>{incidentReport.grounding.unsupported_claims_policy}</strong>
              </div>
            </div>
          ) : (
            <p className="empty-copy">
              {reportError ?? "Generate a report after selecting an incident cluster"}
            </p>
          )}
        </section>

        <section className="detail-panel" aria-label="County detail">
          <div className="section-heading">
            <Layers size={18} aria-hidden="true" />
            <h2>County Selection</h2>
          </div>
          {selectedCounty ? (
            <div className="detail-stack">
              <div>
                <p className="eyebrow">Selected boundary</p>
                <h3>{countyName(selectedCounty)}</h3>
              </div>
              <dl>
                <div>
                  <dt>GEOID</dt>
                  <dd>{selectedCounty.geoid ?? selectedCounty.GEOID ?? "n/a"}</dd>
                </div>
                <div>
                  <dt>County FP</dt>
                  <dd>{selectedCounty.countyfp ?? "n/a"}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <p className="empty-copy">No county selected</p>
          )}
        </section>

        <section className="detail-panel" aria-label="Detection detail">
          <div className="section-heading">
            <SlidersHorizontal size={18} aria-hidden="true" />
            <h2>Detection Detail</h2>
          </div>
          {selectedFire ? (
            <div className="detail-stack">
              <div>
                <p className="eyebrow">{selectedFire.county} County</p>
                <h3>{selectedFire.area_label}</h3>
              </div>
              <dl>
                <div>
                  <dt>Detected</dt>
                  <dd>{selectedFire.acq_datetime.replace("T", " ").replace("Z", " UTC")}</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>{selectedFire.confidence}%</dd>
                </div>
                <div>
                  <dt>Brightness</dt>
                  <dd>{selectedFire.brightness_kelvin} K</dd>
                </div>
                <div>
                  <dt>FRP</dt>
                  <dd>{selectedFire.frp_mw} MW</dd>
                </div>
                <div>
                  <dt>Sensor</dt>
                  <dd>
                    {selectedFire.satellite} / {selectedFire.instrument}
                  </dd>
                </div>
              </dl>
            </div>
          ) : (
            <p className="empty-copy">No detection selected</p>
          )}
        </section>
      </aside>

      <section className="map-stage" aria-label="Arizona wildfire map">
        <div ref={mapContainer} className="map-container" />
        <div className="map-status">
          <Satellite size={16} aria-hidden="true" />
          <span>
            {loading
              ? "Loading detections"
              : `${stats.count} detections visible from ${fires.metadata?.source ?? "source"}`}
          </span>
          {error ? <strong>{error}</strong> : null}
        </div>
      </section>
    </main>
  );
}

export default App;
