'use client';
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useStore } from '../store/useStore';
import { AlertCircle, ShieldAlert, Navigation } from 'lucide-react';
import { useSimulation } from '../hooks/useSimulation';

export default function SimulatorHUD() {
  const {
    isSimulating,
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
    vehicleType,
    setVehicleType,
    etrMinutes,
    detourPossible,
    setEtrMinutes,
    setDetourPossible,
    setActions,
    setAffectedRoads,
    setSpilloverRoads,
    setDetourRoutes,
  } = useStore();

  // Compute remaining ETR based on how far the timeline has advanced from the event's original hour
  const simulatedHour = events.length > 0 ? events[0].timeHour : null;
  const timeDiff = simulatedHour !== null ? Math.max(0, timeOfDayHour - simulatedHour) : 0;
  const remainingEtr = etrMinutes !== null && simulatedHour !== null
    ? Math.max(0, Math.round(etrMinutes - timeDiff * 60))
    : etrMinutes;

  // Ripple Risk decays as time passes, mirroring the visual road healing
  const decayedRiskScore = riskScore !== null
    ? Math.max(0, riskScore * Math.max(0, 1 - timeDiff / 8))
    : null;

  // All fetch + data-transform logic lives in the hook — not here
  const { handleSimulate } = useSimulation();

  return (
    <motion.div 
      initial={{ x: -300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ type: "spring", stiffness: 100 }}
      className="absolute top-8 left-8 w-80 max-h-[calc(100vh-4rem)] overflow-y-auto overflow-x-hidden glass-panel rounded-2xl p-6 text-white flex flex-col gap-6 scrollbar-hide"
    >
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--color-brand-500)] mb-1">Gridlock Traffic Simulation</h1>
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

        {eventCause !== 'Protest / Rally' && eventCause !== 'Waterlogging' && eventCause !== 'Barricade' && eventCause !== 'Police Squad' && eventCause !== 'VMS' && eventCause !== 'Green Wave' && (
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
              <button onClick={() => setEventCause('VMS')} className={`p-2 rounded border ${eventCause === 'VMS' ? 'border-[var(--color-brand-500)] bg-[var(--color-brand-500)]/20 text-[var(--color-brand-500)]' : 'border-gray-700 hover:border-gray-500 text-gray-300'} text-xs font-bold transition-all`}>
                📺 VMS Sign
              </button>
              <button onClick={() => setEventCause('Green Wave')} className={`p-2 rounded border ${eventCause === 'Green Wave' ? 'border-teal-400 bg-teal-400/20 text-teal-400' : 'border-gray-700 hover:border-gray-500 text-gray-300'} text-xs font-bold transition-all`}>
                🚦 Green Wave
              </button>
            </div>
        </div>
      </div>

      <AnimatePresence>
        {riskScore !== null && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="pt-4 border-t border-gray-800 flex flex-col gap-4"
          >
            <div className="flex justify-between items-center bg-black/40 p-3 rounded-xl border border-[var(--color-glass-border)]">
              <span className="text-sm font-medium text-gray-300">Ripple Risk</span>
              <span className={`text-xl font-bold ${decayedRiskScore === 0 ? 'text-green-400' : (decayedRiskScore ?? 0) > 7 ? 'text-red-500' : 'text-orange-400'}`}>
                {decayedRiskScore === 0 ? '✅ Clear' : `${(decayedRiskScore ?? 0).toFixed(1)}`} <span className="text-xs text-gray-500">/ 10</span>
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
              <div className={`flex justify-between items-center p-3 rounded-xl border ${remainingEtr === 0 ? 'bg-green-500/20 border-green-500/30' : 'bg-[var(--color-brand-600)]/20 border-[var(--color-brand-500)]/30'}`}>
                <span className={`text-sm font-medium ${remainingEtr === 0 ? 'text-green-400' : 'text-[var(--color-brand-500)]'}`}>Time to Resolve</span>
                <span className="text-lg font-bold text-white">
                  {remainingEtr === 0 ? '✅ Resolved' : `${remainingEtr} min`}
                </span>
              </div>
            )}
            
            {detourPossible === false && (
              <div className="bg-red-500/20 border border-red-500/50 p-3 rounded-xl text-red-400 text-sm font-bold flex items-center gap-2">
                <ShieldAlert size={18} />
                Critical Chokepoint Blocked: Detour Failed
              </div>
            )}


            
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
