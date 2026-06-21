/**
 * lib/toFeatureCollection.ts
 * --------------------------
 * Converts the raw backend road array into a proper GeoJSON FeatureCollection
 * that Deck.GL's GeoJsonLayer can consume.
 *
 * Lives here — not inlined in a component — so it is testable and reusable.
 */

import { RoadFeature, RoadFeatureCollection } from '../types/api';

/**
 * Takes whatever the backend sends (FeatureCollection, plain array, or null)
 * and always returns a valid GeoJSON FeatureCollection or null.
 */
export function toFeatureCollection(
  data: RoadFeature[] | RoadFeatureCollection | null | undefined
): RoadFeatureCollection | null {
  if (!data) return null;

  // Already a FeatureCollection — return as-is
  if (!Array.isArray(data) && data.type === 'FeatureCollection') {
    return data as RoadFeatureCollection;
  }

  const features = Array.isArray(data) ? data : [];

  return {
    type: 'FeatureCollection',
    features: features.map((f) => {
      // Already a proper GeoJSON Feature
      if (f.type === 'Feature') return f;

      // Raw object — wrap it into a Feature.
      // NOTE: eventHour MUST be read from f.properties, not from f directly.
      //       The backend puts it inside properties. Reading it from the top
      //       level is what caused the invisible-lines bug — never again.
      const props = f.properties ?? {
        color: f.color ?? [255, 50, 50, 220],
        congestion_score: f.congestion_score ?? 5,
        road_id: f.road_id ?? '',
        dynamic_congestion_score: f.dynamic_congestion_score ?? 5,
        decay_factor: f.decay_factor ?? 1.0,
        eventHour: f.eventHour ?? 12, // only used if f.properties is entirely missing
      };

      return {
        type: 'Feature' as const,
        geometry: f.geometry ?? {
          type: 'LineString' as const,
          coordinates: f.coordinates ?? [],
        },
        properties: props,
        road_id: f.road_id,
        coordinates: f.coordinates ?? [],
        congestion_score: f.congestion_score ?? 5,
        dynamic_congestion_score: f.dynamic_congestion_score ?? 5,
        decay_factor: f.decay_factor ?? 1.0,
      };
    }),
  };
}
