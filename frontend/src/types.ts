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
    filters: Record<string, string | number | null>;
  };
}
