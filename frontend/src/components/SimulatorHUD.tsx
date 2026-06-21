'use client';
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useStore } from '../store/useStore';
import { AlertCircle, ShieldAlert, Navigation } from 'lucide-react';
import polyline from '@mapbox/polyline';

export default function SimulatorHUD() {
  const { 
    isSimulating, 
    setIsSimulating, 
    events,
    addEvent,
    clearEvents,
    eventCause,
    setEventCause,
    timeOfDayHour,
    setTimeOfDayHour,
    riskScore, 
    roadClosureProb, 
    setRiskScore, 
    setRoadClosureProb,
    actions,
    setActions,
    vehicleType,
    setVehicleType,
    etrMinutes,
    setEtrMinutes,
    detourPossible,
    setDetourPossible,
    setAffectedRoads,
    setSpilloverRoads,
    setDetourRoutes
  } = useStore();

  const handleSimulate = async () => {
    if (events.length === 0) {
      alert("Please drop at least one pin on the map first!");
      return;
    }

    setIsSimulating(true);
    
    // Reset previous results
    setRiskScore(null);
    setRoadClosureProb(null);
    setEtrMinutes(null);
    setDetourPossible(null);
    setActions([]);
    setAffectedRoads(null);
    setSpilloverRoads(null);
    setDetourRoutes(null);

    try {
      const getCategoryFromHour = (h: number) => {
        if (h >= 7 && h < 11) return 'Morning Peak';
        if (h >= 11 && h < 16) return 'Afternoon';
        if (h >= 16 && h < 21) return 'Evening Peak';
        return 'Night';
      };

      const payload = {
        events: events.map(e => ({
          latitude: e.lat,
          longitude: e.lng,
          event_cause: e.cause,
          time_of_day: getCategoryFromHour(e.timeHour),
          vehicle_type: vehicleType
        }))
      };

      const res = await fetch('/api/simulate_event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const text = await res.text();
        let errorMsg = 'Simulation failed';
        try {
          const errorData = JSON.parse(text);
          errorMsg = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
        } catch {
          errorMsg = text.substring(0, 50) + '...';
        }
        alert(`Error: ${errorMsg}`);
        setIsSimulating(false);
        return;
      }

      const data = await res.json();
      
      // Wrap raw arrays into a proper GeoJSON FeatureCollection for GeoJsonLayer
      const toFeatureCollection = (data: any) => {
        if (!data) return null;
        // Already a FeatureCollection
        if (data.type === 'FeatureCollection') return data;
        // Raw array of feature objects from the backend
        const features = Array.isArray(data) ? data : [];
        return {
          type: 'FeatureCollection',
          features: features.map((f: any) => {
            // Already a proper GeoJSON Feature
            if (f.type === 'Feature') return f;
            // Raw object with coordinates — wrap it
            return {
              type: 'Feature',
              geometry: f.geometry || {
                type: 'LineString',
                coordinates: f.coordinates || []
              },
              properties: f.properties || {
                color: f.color || [255, 50, 50, 200],
                congestion_score: f.congestion_score || 5,
                dynamic_congestion_score: f.dynamic_congestion_score || 5,
                decay_factor: f.decay_factor || 1.0,
                eventHour: f.eventHour || 12,
                road_id: f.road_id || ''
              }
            };
          })
        };
      };

      setRiskScore(data.risk_score);
      setRoadClosureProb(data.requires_road_closure);
      setEtrMinutes(data.etr_minutes);
      setDetourPossible(data.detour_possible);
      setActions(data.recommended_actions);
      setAffectedRoads(toFeatureCollection(data.affected_roads));
      setSpilloverRoads(toFeatureCollection(data.spillover_roads));
      setDetourRoutes(toFeatureCollection(data.detour_routes));
    } catch (error) {
      console.error(error);
      alert("Failed to connect to ML Backend.");
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <motion.div 
      initial={{ x: -300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 100 }}
      className="absolute top-8 left-8 w-80 max-h-[90vh] overflow-y-auto overflow-x-hidden glass-panel rounded-2xl p-6 text-white flex flex-col gap-6 scrollbar-hide"
    >
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--color-brand-500)] mb-1">Traffic Simulation</h1>
        <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold">Event Simulator</p>
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-gray-300">Event Cause</label>
          <select 
            disabled={isSimulating}
            className="bg-black/50 border border-gray-700 rounded-lg p-2 text-sm focus:outline-none focus:border-[var(--color-brand-600)] transition-colors disabled:opacity-50"
            value={eventCause}
            onChange={(e) => setEventCause(e.target.value)}
          >
            <option>Accident</option>
            <option>Vehicle Breakdown</option>
            <option>Protest / Rally</option>
            <option>Waterlogging</option>
          </select>
        </div>

        {eventCause !== 'Protest / Rally' && eventCause !== 'Waterlogging' && eventCause !== 'Barricade' && eventCause !== 'Police Squad' && (
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-300">Vehicle Type</label>
            <select 
              disabled={isSimulating}
              className="bg-black/50 border border-gray-700 rounded-lg p-2 text-sm focus:outline-none focus:border-[var(--color-brand-600)] transition-colors disabled:opacity-50"
              value={vehicleType}
              onChange={(e) => setVehicleType(e.target.value)}
            >
              <option>Car/Taxi</option>
              <option>Heavy Truck</option>
              <option>LCV (Light Commercial)</option>
              <option>Two-Wheeler</option>
            </select>
          </div>
        )}

        <div className="flex flex-col gap-1">
          <div className="flex justify-between">
            <label className="text-sm font-medium text-gray-300">Timeline Scrubber</label>
            <span className="text-xs font-bold text-[var(--color-brand-400)]">{timeOfDayHour.toString().padStart(2, '0')}:00</span>
          </div>
          <input 
            type="range" 
            min="0" 
            max="23" 
            value={timeOfDayHour} 
            onChange={(e) => setTimeOfDayHour(parseInt(e.target.value))}
            className="w-full accent-[var(--color-brand-500)] bg-gray-700 h-1 mt-2 mb-2 rounded-lg appearance-none cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-gray-500 uppercase font-bold tracking-wider">
            <span>Midnight</span>
            <span>Noon</span>
            <span>Midnight</span>
          </div>
        </div>

        <div className="text-xs text-gray-400 flex items-center justify-between mt-2">
          <div className="flex items-center gap-2">
            <Navigation size={14} className={events.length > 0 ? "text-[var(--color-brand-500)]" : "text-gray-500"} />
            {events.length > 0 
              ? `${events.length} event(s) placed` 
              : 'Click map to place events'}
          </div>
          {events.length > 0 && (
            <button 
              onClick={() => { 
                clearEvents(); 
                setRiskScore(null); 
                setActions([]); 
                setAffectedRoads(null); 
                setSpilloverRoads(null);
                setDetourRoutes(null);
                setEtrMinutes(null);
                setDetourPossible(null);
              }}
              className="text-[var(--color-brand-500)] hover:text-white underline"
            >
              Clear
            </button>
          )}
        </div>

        <button 
          onClick={handleSimulate}
          disabled={isSimulating || events.length === 0}
          className={`w-full py-3 rounded-lg font-bold text-sm transition-all shadow-lg flex items-center justify-center gap-2
            ${(isSimulating || events.length === 0) 
              ? 'bg-gray-800 text-gray-500 cursor-not-allowed shadow-none' 
              : 'bg-[var(--color-brand-600)] text-black hover:bg-[var(--color-brand-500)] hover:scale-[1.02] active:scale-95'}`}
        >
          {isSimulating ? (
            <span className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin"></div>
              Calculating Risk...
            </span>
          ) : 'Simulate Impact'}
        </button>

        <div className="flex flex-col gap-2 mt-2 pt-4 border-t border-gray-800">
            <span className="text-xs text-gray-400 uppercase font-bold tracking-wider">Mitigation Resource Bank</span>
            <p className="text-xs text-gray-500 mb-2">Select a resource and drop it on the red roads to divert traffic.</p>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => setEventCause('Barricade')} className={`p-2 rounded border ${eventCause === 'Barricade' ? 'border-[var(--color-brand-500)] bg-[var(--color-brand-500)]/20 text-[var(--color-brand-500)]' : 'border-gray-700 hover:border-gray-500 text-gray-300'} text-xs font-bold transition-all`}>
                🚧 Deploy Barricades
              </button>
              <button onClick={() => setEventCause('Police Squad')} className={`p-2 rounded border ${eventCause === 'Police Squad' ? 'border-[var(--color-brand-500)] bg-[var(--color-brand-500)]/20 text-[var(--color-brand-500)]' : 'border-gray-700 hover:border-gray-500 text-gray-300'} text-xs font-bold transition-all`}>
                👮 Traffic Police
              </button>
            </div>
        </div>
      </div>

      <AnimatePresence>
        {riskScore !== null && (
          <motion.div 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="pt-4 border-t border-gray-800 flex flex-col gap-4 overflow-hidden"
          >
            <div className="flex justify-between items-center bg-black/40 p-3 rounded-xl border border-[var(--color-glass-border)]">
              <span className="text-sm font-medium text-gray-300">Ripple Risk</span>
              <span className={`text-xl font-bold ${riskScore > 7 ? 'text-red-500' : 'text-orange-400'}`}>
                {riskScore.toFixed(1)} <span className="text-xs text-gray-500">/ 10</span>
              </span>
            </div>

            <div className="flex justify-between items-center bg-black/40 p-3 rounded-xl border border-[var(--color-glass-border)]">
              <span className="text-sm font-medium text-gray-300 flex items-center gap-2">
                <ShieldAlert size={16} className="text-orange-400" />
                Closure Prob
              </span>
              <span className="text-lg font-bold text-white">
                {((roadClosureProb || 0) * 100).toFixed(0)}%
              </span>
            </div>

            {etrMinutes !== null && (
              <div className="flex justify-between items-center bg-[var(--color-brand-600)]/20 p-3 rounded-xl border border-[var(--color-brand-500)]/30">
                <span className="text-sm font-medium text-[var(--color-brand-500)]">Time to Resolve</span>
                <span className="text-lg font-bold text-white">
                  {etrMinutes} min
                </span>
              </div>
            )}
            
            {detourPossible === false && (
              <div className="bg-red-500/20 border border-red-500/50 p-3 rounded-xl text-red-400 text-sm font-bold flex items-center gap-2">
                <ShieldAlert size={18} />
                Critical Chokepoint Blocked: Detour Failed
              </div>
            )}

            {actions.length > 0 && (
              <div className="flex flex-col gap-2 mt-2">
                <span className="text-xs text-gray-400 uppercase font-bold tracking-wider">AI Recommendation</span>
                {actions.map((act, idx) => (
                  <div key={idx} className="bg-[var(--color-brand-600)]/10 border border-[var(--color-brand-600)]/30 p-3 rounded-lg text-sm text-[var(--color-brand-500)] flex items-start gap-3">
                    <AlertCircle size={18} className="shrink-0 mt-0.5" />
                    <p>{act.description}</p>
                  </div>
                ))}
              </div>
            )}
            
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
