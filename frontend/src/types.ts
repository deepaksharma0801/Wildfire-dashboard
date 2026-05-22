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
