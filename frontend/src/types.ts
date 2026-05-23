import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";

export interface FireProperties {
  id: string;
  source: string;
  state: string;
  county: string;
  area_label: string;
  latitude: number;
  longitude: number;
  confidence: number;
  brightness_kelvin: number;
  satellite: string;
  instrument: string;
  acq_date: string;
  acq_time: string;
  acq_datetime: string;
  frp_mw: number;
  sample: boolean;
}

export interface FireFeature {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: FireProperties;
}

export interface FireCollection {
  type: "FeatureCollection";
  features: FireFeature[];
  metadata?: {
    count: number;
    source: string;
    requested_data_source?: string;
    raw_count?: number;
    filters: Record<string, string | number | null>;
  };
}

export interface CountyProperties {
  [key: string]: string | number | undefined;
  geoid?: string;
  GEOID?: string;
  name?: string;
  NAME?: string;
  statefp?: string;
  countyfp?: string;
  aland?: number;
  awater?: number;
}

export type CountyFeature = Feature<Polygon | MultiPolygon, CountyProperties>;

export interface CountyCollection extends FeatureCollection<Polygon | MultiPolygon, CountyProperties> {
  metadata?: {
    count: number;
    source: string;
    requested_data_source?: string;
  };
}

export interface FireClusterProperties {
  id: string;
  detection_count: number;
  time_start: string;
  time_end: string;
  avg_confidence: number;
  max_frp_mw: number;
  radius_km: number;
  counties?: string[];
  detection_ids?: string[];
  source: string;
}

export interface FireClusterFeature {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number];
  };
  properties: FireClusterProperties;
}

export interface FireClusterCollection {
  type: "FeatureCollection";
  features: FireClusterFeature[];
  metadata?: {
    count: number;
    source: string;
    requested_data_source?: string;
    cluster_method?: string;
    radius_km?: number;
  };
}

export interface IncidentSummary {
  id: string;
  source: string;
  center: {
    latitude: number;
    longitude: number;
  };
  radius_km: number;
  detection_count: number;
  time_start: string;
  time_end: string;
  avg_confidence: number;
  max_frp_mw: number;
  affected_counties: Array<{
    geoid?: string;
    name: string;
    population?: number;
    households?: number;
    median_household_income?: number;
    estimated_population?: number;
    estimated_households?: number;
    overlap_ratio?: number;
    source?: string;
  }>;
  estimated_population_exposed: number;
  estimated_households_exposed: number;
  weather?: {
    source: string;
    unavailable?: boolean;
    message?: string;
    generated_at?: string;
    current_period?: {
      name?: string;
      start_time?: string;
      temperature?: number;
      temperature_unit?: string;
      wind_speed?: string;
      wind_direction?: string;
      short_forecast?: string;
    } | null;
    next_12h?: {
      max_temperature?: number | null;
      min_temperature?: number | null;
      max_wind_speed_mph?: number | null;
      max_precip_probability?: number | null;
    } | null;
    operational_flags?: string[];
  };
  nearby_places: Array<{
    id: string;
    name: string;
    county?: string;
    population?: number;
    latitude: number;
    longitude: number;
    distance_km: number;
  }>;
  data_caveats: string[];
}

export interface IncidentReport {
  report_id: string;
  mode: "template";
  generated_at: string;
  incident_id: string;
  sections: {
    situation: string;
    exposure: string;
    weather_concerns: string;
    monitoring_priorities: string;
    data_caveats: string;
  };
  grounding: {
    input_source?: string;
    used_fields: string[];
    unsupported_claims_policy: string;
  };
}

export interface RiskCellProperties {
  id: string;
  risk_score: number;
  risk_class: "low" | "moderate" | "high" | "extreme";
  recent_activity: number;
  historical_prior: number;
  intensity: number;
  exposure_proxy: number;
  nearby_detection_count: number;
  horizon_hours: number;
  model_version: string;
}

export type RiskCellFeature = Feature<Polygon, RiskCellProperties>;

export interface RegionConfig {
  code: string;
  label: string;
  fips: string[];
  bbox: [number, number, number, number];
  center: {
    longitude: number;
    latitude: number;
  };
  zoom: number;
}

export interface RegionResponse {
  regions: RegionConfig[];
  default_region: string;
}

export interface H3RiskCellProperties extends RiskCellProperties {
  h3_cell: string;
  h3_resolution: number;
  region: string;
  region_label: string;
  nearest_county: string;
  driver_summary: string;
}

export type H3RiskCellFeature = Feature<Polygon, H3RiskCellProperties>;

export interface H3RiskGridCollection extends FeatureCollection<Polygon, H3RiskCellProperties> {
  metadata?: {
    count: number;
    source: string;
    requested_data_source?: string;
    region: string;
    region_label: string;
    h3_resolution: number;
    model_version: string;
    input_detection_count: number;
    active_region_codes?: string[];
    method: string;
    top_counties: Array<{
      county: string;
      max_risk_score: number;
      avg_risk_score: number;
      cell_count: number;
    }>;
    limitations: string[];
  };
}

export interface RiskScenarioResponse {
  scenario: {
    region: string;
    h3_resolution: number;
    horizon_hours: number;
    temperature_delta_c: number;
    drought_multiplier: number;
    wind_multiplier: number;
    model_version: string;
  };
  overlay: FeatureCollection<Polygon, H3RiskCellProperties & {
    base_risk_score: number;
    scenario_risk_score: number;
    scenario_delta: number;
    scenario_driver_summary: string;
    simulation_model_version: string;
  }>;
  top_cells: Array<{
    h3_cell: string;
    risk_score: number;
    risk_delta: number;
    nearest_county?: string;
    driver_summary: string;
  }>;
  top_counties: Array<{
    county: string;
    max_risk_score: number;
    avg_risk_score: number;
    cell_count: number;
  }>;
  caveats: string[];
}

export interface RiskGridCollection extends FeatureCollection<Polygon, RiskCellProperties> {
  metadata?: {
    count: number;
    source: string;
    requested_data_source?: string;
    model_version: string;
    horizon_hours: number;
    cell_size_deg: number;
    input_detection_count: number;
    historical_prior_source: string;
    method: string;
    limitations: string[];
  };
}

export interface AzCountyRiskRanking {
  rank: number;
  county: string;
  county_name: string;
  geoid: string;
  risk_score: number;
  risk_class: "low" | "moderate" | "high" | "extreme";
  rank_components: {
    risk: number;
    detections: number;
    intensity: number;
    exposure: number;
    trend: number;
  };
  detection_count: number;
  max_frp_mw: number;
  avg_confidence: number;
  population: number;
  households: number;
  max_risk_score: number;
  avg_risk_score: number;
  high_extreme_cell_count: number;
  forecast_trend: "rising" | "stable" | "falling";
  forecast_trend_counts: {
    rising: number;
    stable: number;
    falling: number;
  };
  top_driver: string;
  caveat: string;
}

export interface AzRiskIntelligence {
  model_version: string;
  region: "AZ";
  horizon_hours: number;
  summary: {
    active_detection_count: number;
    county_count: number;
    high_extreme_cell_count: number;
    rising_forecast_cell_count: number;
    highest_risk_county: string | null;
    highest_risk_score: number;
    main_driver: string;
  };
  county_rankings: AzCountyRiskRanking[];
  top_risk_cells: Array<{
    id: string;
    risk_score: number;
    risk_class: string;
    nearby_detection_count: number;
    top_driver: string;
    drivers: Record<string, number>;
  }>;
  driver_breakdown: Record<string, number>;
  data_sources: {
    fires: string;
    counties: string;
    risk_grid: string;
    forecast: string;
    exposure: string;
    requested_data_source: string;
  };
  caveats: string[];
}

export interface ImageryProduct {
  id: string;
  incident_id: string;
  title: string;
  source: string;
  sensor: string;
  before_date: string;
  after_date: string;
  cloud_cover_percent: number;
  bounds: [number, number, number, number];
  burn_area_hectares: number;
  dnbr_mean: number;
  severity_class: string;
  severity_mix: {
    unburned_low: number;
    low: number;
    moderate: number;
    high: number;
  };
  before_image_url: string;
  after_image_url: string;
  burn_scar: FeatureCollection<Polygon, {
    id: string;
    severity: string;
    dnbr_mean: number;
    area_hectares: number;
  }>;
  metadata: {
    source: string;
    method: string;
    limitations: string[];
  };
}

export interface RiskEvaluation {
  model_version: string;
  evaluation_id: string;
  generated_at: string;
  data_source: string;
  cell_size_deg: number;
  sample_size: number;
  positive_proxy_count: number;
  negative_proxy_count: number;
  label_definition: string;
  metrics: {
    roc_auc: number | null;
    classification: {
      threshold: number;
      confusion_matrix: {
        true_positive: number;
        false_positive: number;
        true_negative: number;
        false_negative: number;
      };
      precision: number;
      recall: number;
      specificity: number;
      accuracy: number;
      f1: number;
    };
    top_quartile_capture: {
      bucket_fraction: number;
      cell_count: number;
      positive_proxy_cells_captured: number;
      capture_rate: number;
    };
  };
  feature_importance_proxy: Array<{
    feature: string;
    weight: number;
  }>;
  limitations: string[];
  next_steps: string[];
}

export interface ForecastRiskCellProperties extends RiskCellProperties {
  risk_score_now: number;
  risk_score_forecast: number;
  risk_delta: number;
  trend: "falling" | "stable" | "rising";
  risk_class_forecast: "low" | "moderate" | "high" | "extreme";
  forecast_horizon_hours: 24 | 48 | 72;
  forecast_model_version: string;
  driver_summary: string;
}

export interface ForecastRiskGridCollection extends FeatureCollection<Polygon, ForecastRiskCellProperties> {
  metadata?: {
    count: number;
    source: string;
    requested_data_source?: string;
    base_model_version?: string;
    forecast_model_version: string;
    horizon_hours: 24 | 48 | 72;
    trend_counts: {
      rising: number;
      stable: number;
      falling: number;
    };
    method: string;
    limitations: string[];
  };
}

export interface CopilotResponse {
  query: string;
  intent:
    | "risk_near_population"
    | "county_vulnerability"
    | "recent_fire_clusters"
    | "incident_summary"
    | "help";
  answer: string;
  overlay: FeatureCollection;
  metrics: Record<string, unknown>;
  actions: Array<{
    type: string;
    label: string;
  }>;
  caveats: string[];
}
