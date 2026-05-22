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
  FireCollection,
  FireFeature,
  FireProperties
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

function countyName(properties: CountyProperties) {
  return properties.name ?? properties.NAME ?? "Selected county";
}

function App() {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [fires, setFires] = useState<FireCollection>(emptyCollection);
  const [counties, setCounties] = useState<CountyCollection>(emptyCountyCollection);
  const [selectedFire, setSelectedFire] = useState<FireProperties | null>(null);
  const [selectedCounty, setSelectedCounty] = useState<CountyProperties | null>(null);
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

    return {
      count,
      averageConfidence: count ? Math.round(confidenceTotal / count) : 0,
      peakFrp: peakFrp.toFixed(1)
    };
  }, [fires]);

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
            <span className="layer-dot boundary" />
            <span>Arizona counties</span>
          </div>
          <div className="layer-row muted">
            <span className="layer-dot muted" />
            <span>Risk grid pending</span>
          </div>
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
