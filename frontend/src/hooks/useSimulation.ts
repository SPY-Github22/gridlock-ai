/**
 * hooks/useSimulation.ts
 * ----------------------
 * Custom React hook that owns ALL the simulation API fetch logic.
 *
 * SimulatorHUD.tsx imports this hook and calls handleSimulate().
 * SimulatorHUD knows NOTHING about fetch, JSON, or API URLs.
 *
 * If the API shape changes, only this file and types/api.ts need updating.
 */

'use client';
import { useStore } from '../store/useStore';
import { toFeatureCollection } from '../lib/toFeatureCollection';
import { SimulationResponse, TimeOfDay } from '../types/api';

// ---------------------------------------------------------------------------
// Time-of-day helper
// ---------------------------------------------------------------------------

function getCategoryFromHour(h: number): TimeOfDay {
  if (h >= 7 && h < 11) return 'Morning Peak';
  if (h >= 11 && h < 16) return 'Afternoon';
  if (h >= 16 && h < 21) return 'Evening Peak';
  return 'Night';
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useSimulation() {
  const {
    isSimulating,
    setIsSimulating,
    events,
    vehicleType,
    timeOfDayHour,
    setRiskScore,
    setRoadClosureProb,
    setEtrMinutes,
    setDetourPossible,
    setActions,
    setAffectedRoads,
    setSpilloverRoads,
    setDetourRoutes,
  } = useStore();

  const handleSimulate = async () => {
    if (events.length === 0) {
      alert('Please drop at least one pin on the map first!');
      return;
    }

    // ── Reset previous results ────────────────────────────────────────────
    setIsSimulating(true);
    setRiskScore(null);
    setRoadClosureProb(null);
    setEtrMinutes(null);
    setDetourPossible(null);
    setActions([]);
    setAffectedRoads(null);
    setSpilloverRoads(null);
    setDetourRoutes(null);

    try {
      const payload = {
        events: events.map((e) => ({
          latitude: e.lat,
          longitude: e.lng,
          event_cause: e.cause,
          time_of_day: getCategoryFromHour(e.timeHour),
          vehicle_type: vehicleType,
        })),
      };

      const res = await fetch('/api/simulate_event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const text = await res.text();
        let errorMsg = 'Simulation failed';
        try {
          const errorData = JSON.parse(text);
          errorMsg =
            typeof errorData.detail === 'string'
              ? errorData.detail
              : JSON.stringify(errorData.detail);
        } catch {
          errorMsg = text.substring(0, 100);
        }
        alert(`Error: ${errorMsg}`);
        return;
      }

      const data: SimulationResponse = await res.json();

      // ── Store results ──────────────────────────────────────────────────
      setRiskScore(data.risk_score);
      setRoadClosureProb(data.requires_road_closure);
      setEtrMinutes(data.etr_minutes);
      setDetourPossible(data.detour_possible);
      setActions(data.recommended_actions);

      // toFeatureCollection normalises whatever the backend sends into a
      // proper GeoJSON FeatureCollection for Deck.GL's GeoJsonLayer.
      setAffectedRoads(toFeatureCollection(data.affected_roads));
      setSpilloverRoads(toFeatureCollection(data.spillover_roads));
      setDetourRoutes(toFeatureCollection(data.detour_routes));
    } catch (error) {
      console.error('Simulation error:', error);
      alert('Failed to connect to ML Backend.');
    } finally {
      setIsSimulating(false);
    }
  };

  return { handleSimulate, isSimulating };
}
