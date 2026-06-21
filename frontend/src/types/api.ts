/**
 * types/api.ts
 * ------------
 * TypeScript interfaces that EXACTLY mirror the backend Pydantic response shapes.
 *
 * If the backend changes a field name or type, update it here and TypeScript
 * will immediately flag every place in the frontend that breaks — no more
 * silent runtime bugs like the eventHour fallback issue.
 */

// ---------------------------------------------------------------------------
// Road feature shapes (what the backend sends per road segment)
// ---------------------------------------------------------------------------

/** Properties attached to every road GeoJSON feature from the backend. */
export interface RoadFeatureProperties {
  /** RGBA color array e.g. [180, 0, 0, 220] */
  color: [number, number, number, number];
  congestion_score: number;
  road_id: string;
  dynamic_congestion_score: number;
  decay_factor: number;
  /** Hour-of-day (0–23) the event was simulated at. Used for time-decay coloring. */
  eventHour: number;
}

export interface RoadFeature {
  type: 'Feature';
  geometry: {
    type: 'LineString';
    coordinates: [number, number][]; // [lon, lat] pairs
  };
  properties: RoadFeatureProperties;
  // Top-level aliases (backend sends both; frontend reads from properties)
  road_id?: string;
  coordinates?: [number, number][];
  congestion_score?: number;
  dynamic_congestion_score?: number;
  decay_factor?: number;
  // These are ONLY used as a fallback if properties is entirely missing.
  // Always prefer f.properties.color / f.properties.eventHour.
  color?: [number, number, number, number];
  eventHour?: number;
}

export interface RoadFeatureCollection {
  type: 'FeatureCollection';
  features: RoadFeature[];
}

// ---------------------------------------------------------------------------
// Recommended action
// ---------------------------------------------------------------------------

export interface RecommendedAction {
  action_type: string;
  latitude: number;
  longitude: number;
  description: string;
}

// ---------------------------------------------------------------------------
// Main simulation response
// ---------------------------------------------------------------------------

export interface SimulationResponse {
  risk_score: number;
  requires_road_closure: number; // 0.0–1.0 probability
  etr_minutes: number | null;
  recommended_actions: RecommendedAction[];
  affected_roads: RoadFeature[];
  spillover_roads: RoadFeature[];
  detour_routes: RoadFeature[];
  detour_possible: boolean;
}

// ---------------------------------------------------------------------------
// Request payload
// ---------------------------------------------------------------------------

export type TimeOfDay = 'Morning Peak' | 'Evening Peak' | 'Off-Peak' | 'Afternoon' | 'Night';

export interface EventPayload {
  latitude: number;
  longitude: number;
  event_cause: string;
  time_of_day: TimeOfDay;
  vehicle_type: string;
}

export interface SimulationRequest {
  events: EventPayload[];
}
