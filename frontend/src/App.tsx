import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl, { GeoJSONSource, MapLayerMouseEvent } from "maplibre-gl";
import type { FeatureCollection, Point, Polygon } from "geojson";
import {
  BrainCircuit,
  CalendarDays,
  DatabaseZap,
  Flame,
  Layers,
  RotateCcw,
  Satellite,
  Send,
  SlidersHorizontal,
  TrendingUp
} from "lucide-react";
import {
  AzCountyRiskRanking,
  AzRiskIntelligence,
  CopilotResponse,
  CountyCollection,
  CountyFeature,
  CountyProperties,
  FireClusterCollection,
  FireClusterFeature,
  FireClusterProperties,
  FireCollection,
  FireFeature,
  FireProperties,
  ForecastRiskGridCollection,
  H3RiskCellFeature,
  H3RiskCellProperties,
  H3RiskGridCollection,
  ImageryProduct,
  IncidentReport,
  IncidentSummary,
  RegionConfig,
  RegionResponse,
  RiskScenarioResponse,
  RiskEvaluation,
  RiskCellFeature,
  RiskCellProperties,
  RiskGridCollection
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const defaultRegions: RegionConfig[] = [
  {
    code: "AZ",
    label: "Arizona",
    fips: ["04"],
    bbox: [-115.1, 31.2, -108.8, 37.1],
    center: { longitude: -111.8, latitude: 34.3 },
    zoom: 5.7
  }
];

function boundsCollection(bbox: [number, number, number, number]): FeatureCollection<Polygon> {
  const [west, south, east, north] = bbox;
  return {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [
          [
              [west, south],
              [east, south],
              [east, north],
              [west, north],
              [west, south]
          ]
        ]
      }
    }
  ]
};
}

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

const emptyForecastGrid: ForecastRiskGridCollection = {
  type: "FeatureCollection",
  features: []
};

const emptyH3RiskGrid: H3RiskGridCollection = {
  type: "FeatureCollection",
  features: []
};

const emptyCopilotOverlay: FeatureCollection = {
  type: "FeatureCollection",
  features: []
};

function countyName(properties: CountyProperties) {
  return properties.name ?? properties.NAME ?? "Selected county";
}

function formatNumber(value: number | undefined) {
  return typeof value === "number" ? value.toLocaleString() : "n/a";
}

function collectCoordinatePairs(value: unknown, pairs: Array<[number, number]>) {
  if (!Array.isArray(value)) {
    return;
  }
  if (
    value.length >= 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "number"
  ) {
    pairs.push([value[0], value[1]]);
    return;
  }
  value.forEach((item) => collectCoordinatePairs(item, pairs));
}

function collectionBounds(collection: FeatureCollection): [[number, number], [number, number]] | null {
  const pairs: Array<[number, number]> = [];
  collection.features.forEach((feature) => {
    if (feature.geometry && "coordinates" in feature.geometry) {
      collectCoordinatePairs(feature.geometry.coordinates, pairs);
    }
  });
  if (!pairs.length) {
    return null;
  }
  const longitudes = pairs.map(([longitude]) => longitude);
  const latitudes = pairs.map(([, latitude]) => latitude);
  return [
    [Math.min(...longitudes), Math.min(...latitudes)],
    [Math.max(...longitudes), Math.max(...latitudes)]
  ];
}

function polygonCentroid(feature: H3RiskCellFeature): [number, number] {
  const ring = feature.geometry.coordinates[0] ?? [];
  const coordinates = ring.length > 1 ? ring.slice(0, -1) : ring;
  const total = coordinates.reduce(
    (sum, [longitude, latitude]) => ({
      longitude: sum.longitude + longitude,
      latitude: sum.latitude + latitude
    }),
    { longitude: 0, latitude: 0 }
  );
  const count = Math.max(coordinates.length, 1);
  return [total.longitude / count, total.latitude / count];
}

function riskCellDriverEntries(cell: RiskCellProperties) {
  const entries: Array<[string, number]> = [
    ["Recent activity", cell.recent_activity],
    ["FRP intensity", cell.intensity],
    ["Historical prior", cell.historical_prior],
    ["Exposure proxy", cell.exposure_proxy]
  ];
  return entries.sort((left, right) => right[1] - left[1]);
}

function riskCellExplanation(cell: RiskCellProperties) {
  const [primary, secondary] = riskCellDriverEntries(cell);
  const detectionText =
    cell.nearby_detection_count > 0
      ? `${cell.nearby_detection_count} nearby detections`
      : "no nearby detections";
  return `${cell.risk_class} risk is primarily driven by ${primary[0].toLowerCase()} (${Math.round(
    primary[1] * 100
  )}%) and ${secondary[0].toLowerCase()} (${Math.round(secondary[1] * 100)}%), with ${detectionText}.`;
}

function countyMatchesRanking(properties: CountyProperties, ranking: AzCountyRiskRanking) {
  const geoid = String(properties.geoid ?? properties.GEOID ?? "");
  const name = String(properties.name ?? properties.NAME ?? "").replace(" County", "");
  return geoid === ranking.geoid || name === ranking.county_name;
}

function App() {
  const mapContainer = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [regions, setRegions] = useState<RegionConfig[]>(defaultRegions);
  const [selectedRegionCode, setSelectedRegionCode] = useState("AZ");
  const [fires, setFires] = useState<FireCollection>(emptyCollection);
  const [counties, setCounties] = useState<CountyCollection>(emptyCountyCollection);
  const [clusters, setClusters] = useState<FireClusterCollection>(emptyClusterCollection);
  const [riskGrid, setRiskGrid] = useState<RiskGridCollection>(emptyRiskGrid);
  const [h3RiskGrid, setH3RiskGrid] = useState<H3RiskGridCollection>(emptyH3RiskGrid);
  const [h3Resolution, setH3Resolution] = useState<4 | 5 | 6>(5);
  const [forecastGrid, setForecastGrid] = useState<ForecastRiskGridCollection>(emptyForecastGrid);
  const [selectedFire, setSelectedFire] = useState<FireProperties | null>(null);
  const [selectedCounty, setSelectedCounty] = useState<CountyProperties | null>(null);
  const [selectedCluster, setSelectedCluster] = useState<FireClusterProperties | null>(null);
  const [selectedRiskCell, setSelectedRiskCell] = useState<RiskCellProperties | null>(null);
  const [selectedH3RiskCell, setSelectedH3RiskCell] = useState<H3RiskCellProperties | null>(null);
  const [incidentSummary, setIncidentSummary] = useState<IncidentSummary | null>(null);
  const [incidentReport, setIncidentReport] = useState<IncidentReport | null>(null);
  const [imageryProduct, setImageryProduct] = useState<ImageryProduct | null>(null);
  const [imageryError, setImageryError] = useState<string | null>(null);
  const [azRiskIntelligence, setAzRiskIntelligence] = useState<AzRiskIntelligence | null>(null);
  const [azRiskIntelligenceError, setAzRiskIntelligenceError] = useState<string | null>(null);
  const [riskEvaluation, setRiskEvaluation] = useState<RiskEvaluation | null>(null);
  const [riskEvaluationError, setRiskEvaluationError] = useState<string | null>(null);
  const [forecastHorizon, setForecastHorizon] = useState<24 | 48 | 72>(72);
  const [copilotQuery, setCopilotQuery] = useState("Show wildfire risk near dense population zones in Arizona.");
  const [copilotResponse, setCopilotResponse] = useState<CopilotResponse | null>(null);
  const [copilotOverlay, setCopilotOverlay] = useState<FeatureCollection>(emptyCopilotOverlay);
  const [copilotLoading, setCopilotLoading] = useState(false);
  const [copilotError, setCopilotError] = useState<string | null>(null);
  const [scenarioTemperature, setScenarioTemperature] = useState(3);
  const [scenarioDrought, setScenarioDrought] = useState(1.2);
  const [scenarioWind, setScenarioWind] = useState(1.1);
  const [scenarioResponse, setScenarioResponse] = useState<RiskScenarioResponse | null>(null);
  const [scenarioOverlay, setScenarioOverlay] = useState<FeatureCollection>(emptyCopilotOverlay);
  const [scenarioLoading, setScenarioLoading] = useState(false);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [filters, setFilters] = useState(initialFilters);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectedRegion =
    regions.find((region) => region.code === selectedRegionCode) ?? defaultRegions[0];
  const selectedBbox = selectedRegion.bbox.join(",");
  const regionBounds = useMemo(() => boundsCollection(selectedRegion.bbox), [selectedRegion.bbox]);
  const requestDataSource =
    filters.dataSource === "auto" && selectedRegionCode !== "AZ" ? "sample" : filters.dataSource;
  const isArizonaFocus = selectedRegionCode === "AZ";
  const primaryQuestion = isArizonaFocus
    ? "Which Arizona counties and grid cells need attention?"
    : "Where are the broad Southwest wildfire risk hotspots?";
  const mapReadingHint = isArizonaFocus
    ? "Orange points are fire detections, blue circles group nearby detections, and the shaded grid is the baseline risk layer."
    : "Orange points are fire detections, blue circles group nearby detections, and soft risk hotspots summarize the regional model.";

  function enterArizonaFocus() {
    setSelectedRegionCode("AZ");
    setH3Resolution(5);
    setFilters((current) => ({ ...current, dataSource: "auto" }));
    setCopilotQuery("Summarize wildfire risk across Arizona counties.");
    setSelectedFire(null);
    setSelectedCluster(null);
    setSelectedCounty(null);
    setSelectedRiskCell(null);
    setSelectedH3RiskCell(null);
    setCopilotResponse(null);
    setCopilotOverlay(emptyCopilotOverlay);
    setScenarioResponse(null);
    setScenarioOverlay(emptyCopilotOverlay);
    setIncidentSummary(null);
    setIncidentReport(null);
  }

  function selectAzCountyRanking(ranking: AzCountyRiskRanking) {
    const county = counties.features.find((feature) => countyMatchesRanking(feature.properties, ranking));
    if (!county) {
      return;
    }
    setSelectedCounty(county.properties);
    const map = mapRef.current;
    const bounds = collectionBounds({
      type: "FeatureCollection",
      features: [county]
    });
    if (map && bounds) {
      map.fitBounds(bounds, { padding: 96, maxZoom: 7.2, duration: 700 });
    }
  }

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
    const peakH3Risk = h3RiskGrid.features.reduce(
      (max, feature) => Math.max(max, feature.properties.risk_score),
      0
    );

    return {
      count,
      averageConfidence: count ? Math.round(confidenceTotal / count) : 0,
      peakFrp: peakFrp.toFixed(1),
      peakRisk: (isArizonaFocus ? peakRisk : Math.max(peakRisk, peakH3Risk)).toFixed(0)
    };
  }, [fires, riskGrid, h3RiskGrid, isArizonaFocus]);

  const topForecastCells = useMemo(
    () =>
      [...forecastGrid.features]
        .sort((left, right) => right.properties.risk_delta - left.properties.risk_delta)
        .slice(0, 5),
    [forecastGrid]
  );

  const topH3Cells = useMemo(
    () => [...h3RiskGrid.features].sort((left, right) => right.properties.risk_score - left.properties.risk_score).slice(0, 5),
    [h3RiskGrid]
  );

  const displayedH3RiskGrid = useMemo<H3RiskGridCollection>(() => {
    if (isArizonaFocus) {
      return {
        ...h3RiskGrid,
        features: []
      };
    }

    const minimumScore = selectedRegionCode === "AZ" ? 35 : 42;
    const displayLimit = selectedRegionCode === "southwest" ? 80 : 45;
    const features = [...h3RiskGrid.features]
      .filter(
        (feature) =>
          feature.properties.risk_score >= minimumScore ||
          feature.properties.nearby_detection_count > 0
      )
      .sort((left, right) => right.properties.risk_score - left.properties.risk_score)
      .slice(0, displayLimit);

    return {
      ...h3RiskGrid,
      features
    };
  }, [h3RiskGrid, isArizonaFocus, selectedRegionCode]);

  const displayedH3RiskHotspots = useMemo<FeatureCollection<Point, H3RiskCellProperties>>(
    () => ({
      type: "FeatureCollection",
      features: displayedH3RiskGrid.features.map((feature) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: polygonCentroid(feature)
        },
        properties: feature.properties
      }))
    }),
    [displayedH3RiskGrid]
  );

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

    async function fetchRegions() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/regions`, {
          signal: controller.signal
        });
        if (!response.ok) {
          throw new Error(`Regions API returned ${response.status}`);
        }
        const payload = (await response.json()) as RegionResponse;
        setRegions(payload.regions);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setRegions(defaultRegions);
        }
      }
    }

    fetchRegions();

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncH3RiskLayer = () => {
      const existingSource = map.getSource("h3-risk-grid") as GeoJSONSource | undefined;

      if (existingSource) {
        if (map.getLayer("h3-risk-hotspots")) {
          map.removeLayer("h3-risk-hotspots");
        }
        if (map.getLayer("h3-risk-grid-line")) {
          map.removeLayer("h3-risk-grid-line");
        }
        if (map.getLayer("h3-risk-grid-fill")) {
          map.removeLayer("h3-risk-grid-fill");
        }
        map.removeSource("h3-risk-grid");
      }

      map.addSource("h3-risk-grid", {
        type: "geojson",
        data: displayedH3RiskHotspots
      });

      map.addLayer({
        id: "h3-risk-hotspots",
        type: "circle",
        source: "h3-risk-grid",
        paint: {
          "circle-radius": [
            "interpolate",
            ["linear"],
            ["get", "risk_score"],
            40,
            9,
            60,
            16,
            80,
            26
          ],
          "circle-color": [
            "interpolate",
            ["linear"],
            ["get", "risk_score"],
            35,
            "#fde047",
            55,
            "#fb923c",
            75,
            "#b91c1c"
          ],
          "circle-opacity": [
            "interpolate",
            ["linear"],
            ["get", "risk_score"],
            35,
            0.28,
            55,
            0.48,
            75,
            0.72
          ],
          "circle-blur": 0.25,
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.4,
          "circle-stroke-opacity": 0.85
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);

      map.on("click", "h3-risk-hotspots", (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0] as unknown as H3RiskCellFeature | undefined;
        if (!feature) {
          return;
        }
        setSelectedH3RiskCell(feature.properties);
      });

      map.on("mouseenter", "h3-risk-hotspots", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      map.on("mouseleave", "h3-risk-hotspots", () => {
        map.getCanvas().style.cursor = "";
      });
    };

    if (map.isStyleLoaded()) {
      syncH3RiskLayer();
    } else {
      map.once("load", syncH3RiskLayer);
    }

    const refreshTimer = window.setTimeout(() => {
      const latestMap = mapRef.current;
      if (latestMap?.isStyleLoaded()) {
        syncH3RiskLayer();
        latestMap.triggerRepaint();
      }
    }, 600);

    return () => window.clearTimeout(refreshTimer);
  }, [displayedH3RiskHotspots, h3Resolution, selectedRegionCode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncScenarioLayer = () => {
      const existingSource = map.getSource("scenario-overlay") as GeoJSONSource | undefined;

      if (existingSource) {
        existingSource.setData(scenarioOverlay);
        return;
      }

      map.addSource("scenario-overlay", {
        type: "geojson",
        data: scenarioOverlay
      });

      map.addLayer({
        id: "scenario-overlay-fill",
        type: "fill",
        source: "scenario-overlay",
        filter: [">", ["get", "scenario_delta"], 2],
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "scenario_delta"],
            -15,
            "#64748b",
            0,
            "#f97316",
            20,
            "#dc2626"
          ],
          "fill-opacity": [
            "interpolate",
            ["linear"],
            ["get", "scenario_delta"],
            -10,
            0.12,
            0,
            0.08,
            20,
            0.36
          ]
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);
    };

    if (map.isStyleLoaded()) {
      syncScenarioLayer();
    } else {
      map.once("load", syncScenarioLayer);
    }
  }, [scenarioOverlay]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }
    const [west, south, east, north] = selectedRegion.bbox;
    map.fitBounds(
      [
        [west, south],
        [east, north]
      ],
      { padding: 48, duration: 700, maxZoom: selectedRegion.zoom }
    );
  }, [selectedRegion]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || selectedRegionCode === "AZ") {
      return;
    }

    [
      "county-line",
      "county-fill",
      "risk-grid-line",
      "risk-grid-fill",
      "forecast-grid-line",
      "forecast-grid-fill",
      "burn-scar-line",
      "burn-scar-fill"
    ].forEach((layerId) => {
      if (map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    });

    ["counties", "risk-grid", "forecast-grid", "burn-scar"].forEach((sourceId) => {
      if (map.getSource(sourceId)) {
        map.removeSource(sourceId);
      }
    });

    setSelectedCounty(null);
    setSelectedRiskCell(null);
  }, [selectedRegionCode]);

  useEffect(() => {
    setH3RiskGrid(emptyH3RiskGrid);
    setCopilotQuery(`Show wildfire risk near dense population zones in ${selectedRegion.label}.`);
    setCopilotResponse(null);
    setCopilotOverlay(emptyCopilotOverlay);
    setCopilotError(null);
    setScenarioResponse(null);
    setScenarioOverlay(emptyCopilotOverlay);
    setScenarioError(null);
    setSelectedRiskCell(null);
    setSelectedH3RiskCell(null);
    setSelectedCluster(null);
    setSelectedFire(null);
    setIncidentSummary(null);
    setIncidentReport(null);
  }, [selectedRegionCode, selectedRegion.label]);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchFires() {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({
        bbox: selectedBbox,
        min_confidence: String(filters.minConfidence),
        data_source: requestDataSource
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
  }, [filters, requestDataSource, selectedBbox]);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchClusters() {
      const params = new URLSearchParams({
        bbox: selectedBbox,
        min_confidence: String(filters.minConfidence),
        data_source: requestDataSource,
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
  }, [filters, requestDataSource, selectedBbox]);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchRiskGrid() {
      if (selectedRegionCode !== "AZ") {
        setRiskGrid(emptyRiskGrid);
        setSelectedRiskCell(null);
        return;
      }

      const params = new URLSearchParams({
        bbox: selectedBbox,
        min_confidence: String(filters.minConfidence),
        data_source: requestDataSource,
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
  }, [filters, requestDataSource, selectedBbox, selectedRegionCode]);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchH3RiskGrid() {
      const params = new URLSearchParams({
        region: selectedRegionCode,
        h3_resolution: String(h3Resolution),
        min_confidence: String(filters.minConfidence),
        data_source: requestDataSource
      });

      if (filters.startDate) {
        params.set("start_date", filters.startDate);
      }
      if (filters.endDate) {
        params.set("end_date", filters.endDate);
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/risk/h3-grid?${params}`, {
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`H3 risk API returned ${response.status}`);
        }

        setH3RiskGrid((await response.json()) as H3RiskGridCollection);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setH3RiskGrid(emptyH3RiskGrid);
          setSelectedH3RiskCell(null);
        }
      }
    }

    fetchH3RiskGrid();

    return () => controller.abort();
  }, [filters, h3Resolution, requestDataSource, selectedRegionCode]);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchForecastGrid() {
      if (selectedRegionCode !== "AZ") {
        setForecastGrid(emptyForecastGrid);
        return;
      }

      const params = new URLSearchParams({
        bbox: selectedBbox,
        min_confidence: String(filters.minConfidence),
        data_source: requestDataSource,
        horizon_hours: String(forecastHorizon)
      });

      if (filters.startDate) {
        params.set("start_date", filters.startDate);
      }
      if (filters.endDate) {
        params.set("end_date", filters.endDate);
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/forecast/risk-grid?${params}`, {
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`Forecast API returned ${response.status}`);
        }

        setForecastGrid((await response.json()) as ForecastRiskGridCollection);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setForecastGrid(emptyForecastGrid);
        }
      }
    }

    fetchForecastGrid();

    return () => controller.abort();
  }, [filters, forecastHorizon, requestDataSource, selectedBbox, selectedRegionCode]);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchAzRiskIntelligence() {
      if (!isArizonaFocus) {
        setAzRiskIntelligence(null);
        setAzRiskIntelligenceError(null);
        return;
      }

      const params = new URLSearchParams({
        min_confidence: String(filters.minConfidence),
        data_source: requestDataSource,
        horizon_hours: String(forecastHorizon)
      });

      if (filters.startDate) {
        params.set("start_date", filters.startDate);
      }
      if (filters.endDate) {
        params.set("end_date", filters.endDate);
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/az/risk-intelligence?${params}`, {
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`AZ intelligence API returned ${response.status}`);
        }

        setAzRiskIntelligence((await response.json()) as AzRiskIntelligence);
        setAzRiskIntelligenceError(null);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setAzRiskIntelligence(null);
          setAzRiskIntelligenceError((requestError as Error).message);
        }
      }
    }

    fetchAzRiskIntelligence();

    return () => controller.abort();
  }, [filters, forecastHorizon, isArizonaFocus, requestDataSource]);

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
      selectedH3RiskCell &&
      !h3RiskGrid.features.some((feature) => feature.properties.h3_cell === selectedH3RiskCell.h3_cell)
    ) {
      setSelectedH3RiskCell(null);
    }
  }, [h3RiskGrid, selectedH3RiskCell]);

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
        bbox: selectedBbox,
        min_confidence: String(filters.minConfidence),
        data_source: requestDataSource,
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
  }, [filters, requestDataSource, selectedBbox, selectedCluster]);

  useEffect(() => {
    const controller = new AbortController();
    const incidentId = selectedCluster?.id ?? "sample";

    async function fetchImageryProduct() {
      setImageryError(null);

      try {
        const response = await fetch(`${API_BASE_URL}/api/imagery/${incidentId}/before-after`, {
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`Imagery API returned ${response.status}`);
        }

        setImageryProduct((await response.json()) as ImageryProduct);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setImageryProduct(null);
          setImageryError((requestError as Error).message);
        }
      }
    }

    fetchImageryProduct();

    return () => controller.abort();
  }, [selectedCluster]);

  useEffect(() => {
    const controller = new AbortController();

    async function fetchRiskEvaluation() {
      setRiskEvaluationError(null);

      try {
        const response = await fetch(`${API_BASE_URL}/api/risk/evaluation`, {
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(`Risk evaluation API returned ${response.status}`);
        }

        setRiskEvaluation((await response.json()) as RiskEvaluation);
      } catch (requestError) {
        if ((requestError as Error).name !== "AbortError") {
          setRiskEvaluation(null);
          setRiskEvaluationError((requestError as Error).message);
        }
      }
    }

    fetchRiskEvaluation();

    return () => controller.abort();
  }, []);

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

  async function submitCopilotQuery(queryOverride?: string) {
    const query = queryOverride ?? copilotQuery;
    if (!query.trim()) {
      return;
    }

    setCopilotLoading(true);
    setCopilotError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/copilot/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          data_source: requestDataSource,
          region: selectedRegionCode,
          start_date: filters.startDate || null,
          end_date: filters.endDate || null,
          min_confidence: filters.minConfidence
        })
      });

      if (!response.ok) {
        throw new Error(`Copilot API returned ${response.status}`);
      }

      const payload = (await response.json()) as CopilotResponse;
      setCopilotQuery(query);
      setCopilotResponse(payload);
      setCopilotOverlay(payload.overlay);
      const bounds = collectionBounds(payload.overlay);
      const map = mapRef.current;
      if (bounds && map) {
        map.fitBounds(bounds, { padding: 80, maxZoom: 7.4, duration: 800 });
      }
    } catch (requestError) {
      setCopilotError((requestError as Error).message);
      setCopilotOverlay(emptyCopilotOverlay);
    } finally {
      setCopilotLoading(false);
    }
  }

  async function runScenario() {
    setScenarioLoading(true);
    setScenarioError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/simulations/risk-scenario`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          region: selectedRegionCode,
          h3_resolution: h3Resolution,
          horizon_hours: forecastHorizon,
          temperature_delta_c: scenarioTemperature,
          drought_multiplier: scenarioDrought,
          wind_multiplier: scenarioWind,
          data_source: requestDataSource
        })
      });

      if (!response.ok) {
        throw new Error(`Scenario API returned ${response.status}`);
      }

      const payload = (await response.json()) as RiskScenarioResponse;
      setScenarioResponse(payload);
      setScenarioOverlay(payload.overlay);
      const bounds = collectionBounds(payload.overlay);
      const map = mapRef.current;
      if (bounds && map) {
        map.fitBounds(bounds, { padding: 80, maxZoom: 6.8, duration: 800 });
      }
    } catch (requestError) {
      setScenarioError((requestError as Error).message);
      setScenarioOverlay(emptyCopilotOverlay);
    } finally {
      setScenarioLoading(false);
    }
  }

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncForecastLayer = () => {
      const existingSource = map.getSource("forecast-grid") as GeoJSONSource | undefined;

      if (existingSource) {
        existingSource.setData(forecastGrid);
        return;
      }

      map.addSource("forecast-grid", {
        type: "geojson",
        data: forecastGrid
      });

      map.addLayer({
        id: "forecast-grid-fill",
        type: "fill",
        source: "forecast-grid",
        paint: {
          "fill-color": [
            "match",
            ["get", "trend"],
            "rising",
            "#dc2626",
            "falling",
            "#94a3b8",
            "#f97316"
          ],
          "fill-opacity": [
            "interpolate",
            ["linear"],
            ["get", "risk_delta"],
            -20,
            0.28,
            0,
            0.05,
            20,
            0.34
          ]
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);

      map.addLayer({
        id: "forecast-grid-line",
        type: "line",
        source: "forecast-grid",
        paint: {
          "line-color": "#7c2d12",
          "line-width": 0.6,
          "line-opacity": 0.25
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);
    };

    if (map.isStyleLoaded()) {
      syncForecastLayer();
    } else {
      map.once("load", syncForecastLayer);
    }
  }, [forecastGrid]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncCopilotLayer = () => {
      const existingSource = map.getSource("copilot-overlay") as GeoJSONSource | undefined;

      if (existingSource) {
        existingSource.setData(copilotOverlay);
        return;
      }

      map.addSource("copilot-overlay", {
        type: "geojson",
        data: copilotOverlay
      });

      map.addLayer({
        id: "copilot-overlay-fill",
        type: "fill",
        source: "copilot-overlay",
        paint: {
          "fill-color": "#7c3aed",
          "fill-opacity": 0.22
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);

      map.addLayer({
        id: "copilot-overlay-line",
        type: "line",
        source: "copilot-overlay",
        paint: {
          "line-color": "#5b21b6",
          "line-width": 2,
          "line-opacity": 0.85
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);

      map.addLayer({
        id: "copilot-overlay-points",
        type: "circle",
        source: "copilot-overlay",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "detection_count"], 1, 7, 8, 13],
          "circle-color": "#7c3aed",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
          "circle-opacity": 0.94
        }
      });
    };

    if (map.isStyleLoaded()) {
      syncCopilotLayer();
    } else {
      map.once("load", syncCopilotLayer);
    }
  }, [copilotOverlay]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncBurnScarLayer = () => {
      const burnScar = imageryProduct?.burn_scar ?? {
        type: "FeatureCollection",
        features: []
      };
      const existingSource = map.getSource("burn-scar") as GeoJSONSource | undefined;

      if (existingSource) {
        existingSource.setData(burnScar);
        return;
      }

      map.addSource("burn-scar", {
        type: "geojson",
        data: burnScar
      });

      map.addLayer({
        id: "burn-scar-fill",
        type: "fill",
        source: "burn-scar",
        paint: {
          "fill-color": "#7f1d1d",
          "fill-opacity": 0.38
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);

      map.addLayer({
        id: "burn-scar-line",
        type: "line",
        source: "burn-scar",
        paint: {
          "line-color": "#fef2f2",
          "line-width": 1.6,
          "line-opacity": 0.85
        }
      }, map.getLayer("fire-halos") ? "fire-halos" : undefined);
    };

    if (map.isStyleLoaded()) {
      syncBurnScarLayer();
    } else {
      map.once("load", syncBurnScarLayer);
    }
  }, [imageryProduct]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncRiskLayer = () => {
      if (selectedRegionCode !== "AZ") {
        if (map.getLayer("risk-grid-line")) {
          map.removeLayer("risk-grid-line");
        }
        if (map.getLayer("risk-grid-fill")) {
          map.removeLayer("risk-grid-fill");
        }
        if (map.getSource("risk-grid")) {
          map.removeSource("risk-grid");
        }
        return;
      }

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
  }, [riskGrid, selectedRegionCode]);

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

      if (selectedRegionCode !== "AZ") {
        if (map.getLayer("county-line")) {
          map.removeLayer("county-line");
        }
        if (map.getLayer("county-fill")) {
          map.removeLayer("county-fill");
        }
        if (existingSource) {
          map.removeSource("counties");
        }
        return;
      }

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
  }, [counties, selectedRegionCode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    const syncFireLayer = () => {
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
  }, [fires, regionBounds]);

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Wildfire intelligence controls">
        <header className="brand-block">
          <div className="brand-mark">
            <Flame size={22} aria-hidden="true" />
          </div>
          <div>
            <p className="eyebrow">{isArizonaFocus ? "Arizona focus" : "Southwest scaling"}</p>
            <h1>Wildfire GeoAI</h1>
          </div>
        </header>

        <section className="control-panel" aria-label="Regional scope">
          <div className="section-heading">
            <Layers size={18} aria-hidden="true" />
            <h2>Region</h2>
          </div>
          <label>
            <span>Operational area</span>
            <select
              value={selectedRegionCode}
              onChange={(event) => {
                const nextRegion = event.target.value;
                setSelectedRegionCode(nextRegion);
                setH3Resolution(nextRegion === "AZ" ? 5 : 4);
                setSelectedFire(null);
                setSelectedCluster(null);
                setSelectedCounty(null);
                setSelectedRiskCell(null);
                setSelectedH3RiskCell(null);
              }}
            >
              {regions.map((region) => (
                <option key={region.code} value={region.code}>
                  {region.label}
                </option>
              ))}
            </select>
          </label>
          <div className="source-card">
            <span>Selected bbox</span>
            <strong>{selectedBbox}</strong>
          </div>
        </section>

        <section
          className={`control-panel arizona-focus-panel${isArizonaFocus ? " active" : ""}`}
          aria-label="Arizona focus mode"
        >
          <div className="section-heading">
            <Flame size={18} aria-hidden="true" />
            <h2>Arizona Focus</h2>
          </div>
          <div className="focus-summary">
            <p>
              {isArizonaFocus
                ? "Detailed Arizona mode is active."
                : "Switch to the Arizona drill-down workspace."}
            </p>
            <dl>
              <div>
                <dt>Scope</dt>
                <dd>AZ only</dd>
              </div>
              <div>
                <dt>Detail layers</dt>
                <dd>Counties + grid</dd>
              </div>
              <div>
                <dt>Imagery demo</dt>
                <dd>Enabled</dd>
              </div>
            </dl>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={enterArizonaFocus}
            disabled={isArizonaFocus}
          >
            <Flame size={16} aria-hidden="true" />
            {isArizonaFocus ? "Arizona focus active" : "Open Arizona focus"}
          </button>
        </section>

        <section className="control-panel guide-panel" aria-label="Dashboard guide">
          <div className="section-heading">
            <BrainCircuit size={18} aria-hidden="true" />
            <h2>Start Here</h2>
          </div>
          <div className="guide-summary">
            <strong>{primaryQuestion}</strong>
            <p>{mapReadingHint}</p>
          </div>
          <div className="workflow-list">
            <div>
              <span>1</span>
              <p>{isArizonaFocus ? "Read AZ Intelligence for the top counties." : "Scan the regional hotspots."}</p>
            </div>
            <div>
              <span>2</span>
              <p>{isArizonaFocus ? "Click a county, grid cell, detection, or cluster." : "Open Arizona Focus for deeper drill-down."}</p>
            </div>
            <div>
              <span>3</span>
              <p>{isArizonaFocus ? "Use Incident Summary and AI Report after selecting a cluster." : "Ask Copilot a spatial question or run a scenario."}</p>
            </div>
          </div>
        </section>

        {isArizonaFocus ? (
          <section className="detail-panel az-intelligence-panel" aria-label="Arizona risk intelligence">
            <div className="section-heading">
              <TrendingUp size={18} aria-hidden="true" />
              <h2>AZ Intelligence</h2>
            </div>
            {azRiskIntelligence ? (
              <div className="az-intelligence-stack">
                <dl>
                  <div>
                    <dt>Highest county</dt>
                    <dd>{azRiskIntelligence.summary.highest_risk_county ?? "n/a"}</dd>
                  </div>
                  <div>
                    <dt>High/extreme cells</dt>
                    <dd>{azRiskIntelligence.summary.high_extreme_cell_count}</dd>
                  </div>
                  <div>
                    <dt>Rising forecast cells</dt>
                    <dd>{azRiskIntelligence.summary.rising_forecast_cell_count}</dd>
                  </div>
                  <div>
                    <dt>Main driver</dt>
                    <dd>{azRiskIntelligence.summary.main_driver}</dd>
                  </div>
                </dl>
                <div className="county-risk-list">
                  <span>Top county risk</span>
                  {azRiskIntelligence.county_rankings.slice(0, 5).map((county) => (
                    <button
                      key={county.geoid || county.county}
                      type="button"
                      className="county-risk-row"
                      onClick={() => selectAzCountyRanking(county)}
                    >
                      <strong>
                        #{county.rank} {county.county_name}
                      </strong>
                      <span>{county.risk_score}/100 · {county.forecast_trend}</span>
                      <em>
                        {county.detection_count} detections · {county.population.toLocaleString()} pop · {county.top_driver}
                      </em>
                    </button>
                  ))}
                </div>
                <p className="diagnostic-note">{azRiskIntelligence.caveats[0]}</p>
              </div>
            ) : (
              <p className="empty-copy">{azRiskIntelligenceError ?? "Loading Arizona risk intelligence"}</p>
            )}
          </section>
        ) : null}

        <section className="control-panel copilot-panel" aria-label="Spatial AI Copilot">
          <div className="section-heading">
            <BrainCircuit size={18} aria-hidden="true" />
            <h2>Spatial Copilot</h2>
          </div>
          <form
            className="copilot-form"
            onSubmit={(event) => {
              event.preventDefault();
              submitCopilotQuery();
            }}
          >
            <textarea
              value={copilotQuery}
              onChange={(event) => setCopilotQuery(event.target.value)}
              rows={3}
              aria-label="Spatial copilot query"
            />
            <button className="icon-button" type="submit" disabled={copilotLoading}>
              <Send size={16} aria-hidden="true" />
              {copilotLoading ? "Thinking" : "Ask copilot"}
            </button>
          </form>
          <div className="example-chip-row" aria-label="Copilot examples">
            {[
              `Show wildfire risk near dense population zones in ${selectedRegion.label}.`,
              `Which areas have the highest wildfire risk in ${selectedRegion.label}?`,
              "Show recent active fire clusters."
            ].map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => submitCopilotQuery(example)}
              >
                {example}
              </button>
            ))}
          </div>
          {copilotResponse ? (
            <div className="copilot-answer">
              <p className="eyebrow">{copilotResponse.intent.replace("_", " ")}</p>
              <p>{copilotResponse.answer}</p>
              <strong>{copilotResponse.overlay.features.length} overlay features applied</strong>
            </div>
          ) : (
            <p className="empty-copy">{copilotError ?? "Ask a spatial question to generate an overlay"}</p>
          )}
        </section>

        <section className="metric-grid" aria-label="Detection metrics">
          <div className="metric-tile">
            <span>Fire detections</span>
            <strong>{stats.count}</strong>
          </div>
          <div className="metric-tile">
            <span>Avg detection confidence</span>
            <strong>{stats.averageConfidence}%</strong>
          </div>
          <div className="metric-tile">
            <span>Peak fire intensity</span>
            <strong>{stats.peakFrp}</strong>
          </div>
          <div className="metric-tile">
            <span>Incident groups</span>
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
            <span>Fire data</span>
            <strong>{fires.metadata?.source ?? "pending"}</strong>
          </div>
          <div className="source-card">
            <span>Boundary data</span>
            <strong>{counties.metadata?.source ?? "pending"}</strong>
          </div>
          <div className="source-card">
            <span>Incident grouping</span>
            <strong>{clusters.metadata?.cluster_method ?? "pending"}</strong>
          </div>
          <div className="source-card">
            <span>Risk model</span>
            <strong>{riskGrid.metadata?.model_version ?? "pending"}</strong>
          </div>
          {!isArizonaFocus ? (
            <>
              <div className="source-card">
                <span>H3 model</span>
                <strong>{h3RiskGrid.metadata?.model_version ?? "pending"}</strong>
              </div>
              <div className="source-card">
                <span>Active data footprint</span>
                <strong>{h3RiskGrid.metadata?.active_region_codes?.join(", ") || selectedRegionCode}</strong>
              </div>
            </>
          ) : null}
          <div className="source-card">
            <span>Risk evaluation</span>
            <strong>{riskEvaluation?.evaluation_id ?? "pending"}</strong>
          </div>
          <div className="source-card">
            <span>Forecast model</span>
            <strong>{forecastGrid.metadata?.forecast_model_version ?? "pending"}</strong>
          </div>
          <div className="source-card">
            <span>Copilot intent</span>
            <strong>{copilotResponse?.intent ?? "pending"}</strong>
          </div>
          {!isArizonaFocus ? (
            <div className="source-card">
              <span>Scenario model</span>
              <strong>{scenarioResponse?.scenario.model_version ?? "pending"}</strong>
            </div>
          ) : null}
          <div className="source-card">
            <span>Imagery source</span>
            <strong>{imageryProduct?.metadata.source ?? "pending"}</strong>
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
            <span>Incident groups</span>
          </div>
          <div className="layer-row">
            <span className="layer-dot boundary" />
            <span>{selectedRegion.label} boundaries</span>
          </div>
          <div className="layer-row">
            <span className="layer-dot risk" />
            <span>Risk grid</span>
          </div>
          {!isArizonaFocus ? (
            <div className="layer-row">
              <span className="layer-dot h3" />
              <span>Risk hotspots</span>
            </div>
          ) : null}
          {!isArizonaFocus ? (
            <div className="layer-row">
              <span className="layer-dot scenario" />
              <span>What-if scenario</span>
            </div>
          ) : null}
          <div className="layer-row">
            <span className="layer-dot forecast" />
            <span>Forecast trend</span>
          </div>
          <div className="layer-row">
            <span className="layer-dot copilot" />
            <span>Copilot overlay</span>
          </div>
          <div className="layer-row">
            <span className="layer-dot burn" />
            <span>Burn scar mask</span>
          </div>
        </section>

        {!isArizonaFocus ? (
          <section className="detail-panel" aria-label="Regional risk hotspots">
            <div className="section-heading">
              <TrendingUp size={18} aria-hidden="true" />
              <h2>Regional Risk</h2>
            </div>
            <div className="segmented-control" aria-label="H3 resolution">
              {[4, 5, 6].map((resolution) => (
                <button
                  key={resolution}
                  type="button"
                  className={h3Resolution === resolution ? "selected" : ""}
                  onClick={() => setH3Resolution(resolution as 4 | 5 | 6)}
                >
                  r{resolution}
                </button>
              ))}
            </div>
            <dl>
              <div>
                <dt>Shown hotspots</dt>
                <dd>{displayedH3RiskGrid.features.length}</dd>
              </div>
              <div>
                <dt>Model cells</dt>
                <dd>{h3RiskGrid.metadata?.count ?? 0}</dd>
              </div>
              <div>
                <dt>Resolution</dt>
                <dd>{h3RiskGrid.metadata?.h3_resolution ?? h3Resolution}</dd>
              </div>
            </dl>
            <div className="forecast-list">
              <span>Top risk cells</span>
              {topH3Cells.map((feature) => (
                <div key={feature.properties.h3_cell} className="forecast-row">
                  <strong>{feature.properties.nearest_county}</strong>
                  <em>{feature.properties.risk_score}/100</em>
                </div>
              ))}
            </div>
            <div className="forecast-list">
              <span>Top county proxies</span>
              {(h3RiskGrid.metadata?.top_counties ?? []).slice(0, 5).map((row) => (
                <div key={row.county} className="forecast-row">
                  <strong>{row.county}</strong>
                  <em>{row.max_risk_score}/100</em>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        {!isArizonaFocus ? (
          <section className="detail-panel" aria-label="What-if risk simulation">
            <div className="section-heading">
              <SlidersHorizontal size={18} aria-hidden="true" />
              <h2>What-If</h2>
            </div>
            <div className="range-row">
              <div>
                <span>Temperature delta</span>
                <strong>{scenarioTemperature > 0 ? "+" : ""}{scenarioTemperature}°C</strong>
              </div>
              <input
                type="range"
                min="-3"
                max="6"
                step="1"
                value={scenarioTemperature}
                onChange={(event) => setScenarioTemperature(Number(event.target.value))}
              />
            </div>
            <div className="range-row">
              <div>
                <span>Drought multiplier</span>
                <strong>x{scenarioDrought.toFixed(1)}</strong>
              </div>
              <input
                type="range"
                min="0.7"
                max="1.8"
                step="0.1"
                value={scenarioDrought}
                onChange={(event) => setScenarioDrought(Number(event.target.value))}
              />
            </div>
            <div className="range-row">
              <div>
                <span>Wind multiplier</span>
                <strong>x{scenarioWind.toFixed(1)}</strong>
              </div>
              <input
                type="range"
                min="0.7"
                max="1.8"
                step="0.1"
                value={scenarioWind}
                onChange={(event) => setScenarioWind(Number(event.target.value))}
              />
            </div>
            <button className="icon-button" type="button" onClick={runScenario} disabled={scenarioLoading}>
              <TrendingUp size={16} aria-hidden="true" />
              {scenarioLoading ? "Running scenario" : "Run scenario"}
            </button>
            {scenarioResponse ? (
              <div className="forecast-list">
                <span>Scenario top cells</span>
                {scenarioResponse.top_cells.slice(0, 5).map((cell) => (
                  <div key={cell.h3_cell} className="forecast-row">
                    <strong>{cell.nearest_county ?? cell.h3_cell.slice(0, 7)}</strong>
                    <em>
                      {cell.risk_delta > 0 ? "+" : ""}
                      {cell.risk_delta}
                    </em>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-copy">{scenarioError ?? "Run a scenario to compare risk under changed conditions"}</p>
            )}
          </section>
        ) : null}

        <section className="detail-panel" aria-label="Risk forecast">
          <div className="section-heading">
            <TrendingUp size={18} aria-hidden="true" />
            <h2>Forecast</h2>
          </div>
          <div className="segmented-control" aria-label="Forecast horizon">
            {[24, 48, 72].map((horizon) => (
              <button
                key={horizon}
                type="button"
                className={forecastHorizon === horizon ? "selected" : ""}
                onClick={() => setForecastHorizon(horizon as 24 | 48 | 72)}
              >
                {horizon}h
              </button>
            ))}
          </div>
          <dl>
            <div>
              <dt>Rising</dt>
              <dd>{forecastGrid.metadata?.trend_counts.rising ?? 0}</dd>
            </div>
            <div>
              <dt>Stable</dt>
              <dd>{forecastGrid.metadata?.trend_counts.stable ?? 0}</dd>
            </div>
            <div>
              <dt>Falling</dt>
              <dd>{forecastGrid.metadata?.trend_counts.falling ?? 0}</dd>
            </div>
          </dl>
          <div className="forecast-list">
            <span>Top projected changes</span>
            {topForecastCells.map((feature) => (
              <div key={feature.properties.id} className="forecast-row">
                <strong>{feature.properties.id}</strong>
                <em>
                  {feature.properties.trend} · {feature.properties.risk_delta > 0 ? "+" : ""}
                  {feature.properties.risk_delta}
                </em>
              </div>
            ))}
          </div>
        </section>

        <section className="detail-panel" aria-label="Satellite burn scar analysis">
          <div className="section-heading">
            <Satellite size={18} aria-hidden="true" />
            <h2>Satellite Analysis</h2>
          </div>
          {imageryProduct ? (
            <div className="imagery-stack">
              <div>
                <p className="eyebrow">{imageryProduct.sensor}</p>
                <h3>{imageryProduct.title}</h3>
              </div>
              <div className="imagery-compare">
                <figure>
                  <img src={`${API_BASE_URL}${imageryProduct.before_image_url}`} alt="Before satellite sample" />
                  <figcaption>Before · {imageryProduct.before_date}</figcaption>
                </figure>
                <figure>
                  <img src={`${API_BASE_URL}${imageryProduct.after_image_url}`} alt="After satellite sample" />
                  <figcaption>After · {imageryProduct.after_date}</figcaption>
                </figure>
              </div>
              <dl>
                <div>
                  <dt>Burn area</dt>
                  <dd>{imageryProduct.burn_area_hectares.toLocaleString()} ha</dd>
                </div>
                <div>
                  <dt>Mean dNBR</dt>
                  <dd>{imageryProduct.dnbr_mean}</dd>
                </div>
                <div>
                  <dt>Severity</dt>
                  <dd>{imageryProduct.severity_class}</dd>
                </div>
                <div>
                  <dt>Cloud cover</dt>
                  <dd>{imageryProduct.cloud_cover_percent}%</dd>
                </div>
              </dl>
              <div className="severity-bars" aria-label="Burn severity mix">
                {Object.entries(imageryProduct.severity_mix).map(([label, value]) => (
                  <div key={label}>
                    <span>{label.replace("_", " ")}</span>
                    <strong style={{ width: `${value}%` }}>{value}%</strong>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="empty-copy">{imageryError ?? "Loading sample imagery product"}</p>
          )}
        </section>

        <section className="detail-panel" aria-label="Risk grid detail">
          <div className="section-heading">
            <SlidersHorizontal size={18} aria-hidden="true" />
            <h2>Risk Layer</h2>
          </div>
          {selectedH3RiskCell ? (
            <div className="detail-stack">
              <div>
                <p className="eyebrow">H3 {selectedH3RiskCell.h3_resolution} · {selectedH3RiskCell.region_label}</p>
                <h3>{selectedH3RiskCell.risk_class} risk</h3>
              </div>
              <dl>
                <div>
                  <dt>Score</dt>
                  <dd>{selectedH3RiskCell.risk_score}/100</dd>
                </div>
                <div>
                  <dt>H3 cell</dt>
                  <dd>{selectedH3RiskCell.h3_cell.slice(0, 8)}</dd>
                </div>
                <div>
                  <dt>Nearest county</dt>
                  <dd>{selectedH3RiskCell.nearest_county}</dd>
                </div>
                <div>
                  <dt>Nearby detections</dt>
                  <dd>{selectedH3RiskCell.nearby_detection_count}</dd>
                </div>
              </dl>
              <p className="diagnostic-note">{selectedH3RiskCell.driver_summary}</p>
            </div>
          ) : selectedRiskCell ? (
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
                  <dt>Exposure proxy</dt>
                  <dd>{Math.round(selectedRiskCell.exposure_proxy * 100)}%</dd>
                </div>
                <div>
                  <dt>Nearby detections</dt>
                  <dd>{selectedRiskCell.nearby_detection_count}</dd>
                </div>
              </dl>
              <div className="feature-weight-list">
                {riskCellDriverEntries(selectedRiskCell).map(([label, value]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <strong style={{ width: `${Math.max(Math.round(value * 100), 8)}%` }}>
                      {Math.round(value * 100)}%
                    </strong>
                  </div>
                ))}
              </div>
              <p className="diagnostic-note">{riskCellExplanation(selectedRiskCell)}</p>
              <p className="diagnostic-note">
                FIRMS hotspots are not fire perimeters; this baseline score is screening context only.
              </p>
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

        <section className="detail-panel" aria-label="Risk model diagnostics">
          <div className="section-heading">
            <DatabaseZap size={18} aria-hidden="true" />
            <h2>Model Diagnostics</h2>
          </div>
          {riskEvaluation ? (
            <div className="diagnostics-stack">
              <div>
                <p className="eyebrow">{riskEvaluation.model_version}</p>
                <h3>Proxy backtest</h3>
              </div>
              <dl>
                <div>
                  <dt>ROC AUC</dt>
                  <dd>{riskEvaluation.metrics.roc_auc ?? "n/a"}</dd>
                </div>
                <div>
                  <dt>Precision</dt>
                  <dd>{riskEvaluation.metrics.classification.precision}</dd>
                </div>
                <div>
                  <dt>Recall</dt>
                  <dd>{riskEvaluation.metrics.classification.recall}</dd>
                </div>
                <div>
                  <dt>F1</dt>
                  <dd>{riskEvaluation.metrics.classification.f1}</dd>
                </div>
                <div>
                  <dt>Sample cells</dt>
                  <dd>{riskEvaluation.sample_size}</dd>
                </div>
              </dl>
              <div className="feature-weight-list">
                {riskEvaluation.feature_importance_proxy.map((item) => (
                  <div key={item.feature}>
                    <span>{item.feature.replace("_", " ")}</span>
                    <strong style={{ width: `${Math.round(item.weight * 100)}%` }}>
                      {Math.round(item.weight * 100)}%
                    </strong>
                  </div>
                ))}
              </div>
              <p className="diagnostic-note">{riskEvaluation.limitations[0]}</p>
            </div>
          ) : (
            <p className="empty-copy">{riskEvaluationError ?? "Loading model diagnostics"}</p>
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

      <section className="map-stage" aria-label={`${selectedRegion.label} wildfire map`}>
        <div ref={mapContainer} className="map-container" />
        <div className="map-status">
          <Satellite size={16} aria-hidden="true" />
          <span>
            {loading
              ? "Loading detections"
              : `${stats.count} detections visible in ${selectedRegion.label} from ${fires.metadata?.source ?? "source"}`}
          </span>
          {error ? <strong>{error}</strong> : null}
        </div>
        <div className="map-legend-card" aria-label="Map legend">
          <strong>{isArizonaFocus ? "Arizona map" : "Regional map"}</strong>
          <div><span className="legend-dot fire" />Fire detection</div>
          <div><span className="legend-dot cluster" />Incident group</div>
          {isArizonaFocus ? (
            <>
              <div><span className="legend-line boundary" />County boundary</div>
              <div><span className="legend-swatch high" />Higher risk grid</div>
            </>
          ) : (
            <div><span className="legend-dot hotspot" />Risk hotspot</div>
          )}
        </div>
      </section>
    </main>
  );
}

export default App;
