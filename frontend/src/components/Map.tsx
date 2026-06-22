'use client';
import React, { useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { Map as MapGL } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { ScatterplotLayer, GeoJsonLayer } from '@deck.gl/layers';
import { useStore } from '../store/useStore';

/**
 * Simulates congestion healing over time.
 *
 * At t=0 (event just happened): full original color (red/orange/purple)
 * t=1-3 hrs later:  shifts toward amber/yellow
 * t=3-5 hrs later:  shifts to green  (traffic clearing)
 * t=5-8 hrs later:  green fades out  (road fully recovered)
 * t>8 hrs or before event: invisible
 *
 * @param baseColor  RGBA color from the backend [r,g,b,a]
 * @param eventHour  Hour the event was simulated at
 * @param nowHour    Current position of the timeline scrubber
 */
function getTimeDecayedColor(
  baseColor: number[],
  eventHour: number,
  nowHour: number
): [number, number, number, number] {
  const timeDiff = nowHour - eventHour;

  // Before event happened — don't draw
  if (timeDiff < -1) return [0, 0, 0, 0];

  // At event time (±1 hr) — full original color
  if (timeDiff <= 1) {
    return [baseColor[0], baseColor[1], baseColor[2], baseColor[3] ?? 220];
  }

  // 1–3 hrs: shift toward amber/orange
  if (timeDiff <= 3) {
    const t = (timeDiff - 1) / 2; // 0 → 1
    return [
      Math.round(lerp(baseColor[0], 255, t)),
      Math.round(lerp(baseColor[1], 165, t)),
      Math.round(lerp(baseColor[2], 0,   t)),
      baseColor[3] ?? 220,
    ];
  }

  // 3–5 hrs: amber → green
  if (timeDiff <= 5) {
    const t = (timeDiff - 3) / 2; // 0 → 1
    return [
      Math.round(lerp(255, 50,  t)),
      Math.round(lerp(165, 200, t)),
      Math.round(lerp(0,   50,  t)),
      baseColor[3] ?? 220,
    ];
  }

  // 5–8 hrs: green fades out
  if (timeDiff <= 8) {
    const alpha = Math.max(0, 1 - (timeDiff - 5) / 3);
    return [50, 200, 50, Math.round(220 * alpha)];
  }

  // Fully recovered
  return [0, 0, 0, 0];
}

/** Linear interpolation helper */
function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Line width also shrinks as congestion heals — thick at peak, thin when green.
 */
function getTimeDecayedWidth(
  baseWidth: number,
  eventHour: number,
  nowHour: number
): number {
  const timeDiff = nowHour - eventHour;
  if (timeDiff < -1) return 0;
  if (timeDiff <= 1) return baseWidth;
  if (timeDiff <= 5) return baseWidth * Math.max(0.35, 1 - (timeDiff - 1) * 0.16);
  if (timeDiff <= 8) return baseWidth * 0.35 * Math.max(0, 1 - (timeDiff - 5) / 3);
  return 0;
}

const INITIAL_VIEW_STATE = {
  longitude: 77.5946,
  latitude: 12.9716,
  zoom: 11,
  pitch: 45,
  bearing: 0
};

// Free Dark Matter basemap from CARTO (no Mapbox token required)
const BASEMAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

export default function GeospatialMap() {
  const events = useStore(state => state.events);
  const addEvent = useStore(state => state.addEvent);
  const eventCause = useStore(state => state.eventCause);
  const timeOfDayHour = useStore(state => state.timeOfDayHour);
  const riskScore = useStore(state => state.riskScore);
  const setHoveredEvent = useStore(state => state.setHoveredEvent);
  const hoveredEvent = useStore(state => state.hoveredEvent);
  const actions = useStore(state => state.actions);
  const affectedRoads = useStore(state => state.affectedRoads);
  const spilloverRoads = useStore(state => state.spilloverRoads);
  const detourRoutes = useStore(state => state.detourRoutes);
  const isSimulating = useStore(state => state.isSimulating);

  const [pulseFactor, setPulseFactor] = useState(1.0);

  React.useEffect(() => {
    let animationId: number;
    const startTime = Date.now();
    const animate = () => {
      const elapsed = (Date.now() - startTime) / 1000;
      // Pulse factor between 0.85 and 1.15
      const factor = 1.0 + 0.15 * Math.sin(elapsed * Math.PI * 2);
      setPulseFactor(factor);
      animationId = requestAnimationFrame(animate);
    };
    animationId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationId);
  }, []);

  const handleMapClick = (info: any) => {
    // Only allow placing pin if we are not currently waiting for API
    if (info.coordinate && !isSimulating) {
      const isAccident = eventCause === 'Accident' || eventCause === 'Vehicle Breakdown';
      addEvent({
        id: Date.now(),
        lng: info.coordinate[0], 
        lat: info.coordinate[1],
        cause: eventCause,
        vehicleType: isAccident ? useStore.getState().vehicleType : undefined,
        timeHour: timeOfDayHour
      });
    }
  };

  const [roadNetwork, setRoadNetwork] = useState<any>(null);

  React.useEffect(() => {
    // Fetch the road network overlay on mount
    fetch('/api/network')
      .then(res => res.json())
      .then(data => {
        if (data.type === 'FeatureCollection') {
          setRoadNetwork(data);
        }
      })
      .catch(err => console.error("Failed to load road network overlay", err));
  }, []);

  const layers = useMemo(() => {
    const arr = [];

    // 0. The World Mask (Inverted Polygon)
    arr.push(
      new GeoJsonLayer({
        id: 'world-mask-layer',
        data: '/mask.geojson',
        filled: true,
        getFillColor: [0, 0, 0, 240], // 95% opacity black covering the world
        stroked: true,
        getLineColor: [0, 240, 255, 100], // Subtle neon border around Bangalore
        lineWidthMinPixels: 2
      })
    );

    // 0.5 Road Network Overlay
    if (roadNetwork) {
      arr.push(
        new GeoJsonLayer({
          id: 'road-network-overlay',
          data: roadNetwork,
          stroked: true,
          filled: false,
          lineWidthMinPixels: 1,
          getLineColor: (f: any) => f.properties.color || [100, 100, 100, 100],
          pickable: false,
        })
      );
    }

    // 1. The Pin Layer (Scatterplot)
    if (events.length > 0) {
      arr.push(
        new ScatterplotLayer({
          id: 'pin-layer',
          data: events,
          getPosition: d => [d.lng, d.lat],
          getFillColor: d => {
            if (d.cause === 'Barricade') return [255, 165, 0, 220]; // Orange
            if (d.cause === 'Police Squad') return [65, 105, 225, 220]; // Royal Blue
            if (d.cause === 'VMS') return [255, 20, 147, 220]; // Deep Pink for VMS
            if (d.cause === 'Green Wave') return [0, 255, 255, 220]; // Cyan for Green Wave
            return [0, 240, 255, 200]; // Brand Neon Blue for Hazards
          },
          getRadius: (d) => {
            if (d.cause === 'Barricade' || d.cause === 'Police Squad' || d.cause === 'VMS' || d.cause === 'Green Wave') return 30;
            
            let baseRadius = 30;
            if (d.cause === 'Waterlogging') baseRadius = 600;
            else if (d.cause === 'VIP Movement') baseRadius = 50;
            else if (d.cause === 'Protest / Rally') baseRadius = 200;
            else if (d.cause === 'Accident' || d.cause === 'Vehicle Breakdown') {
              if (d.vehicleType === 'Two-Wheeler') baseRadius = 80;
              else if (d.vehicleType === 'Heavy Truck') baseRadius = 400;
              else if (d.vehicleType === 'LCV (Light Commercial)') baseRadius = 200;
              else baseRadius = 150; // Car/Taxi
            }
            
            // Add slight risk score inflation
            baseRadius += ((riskScore ?? 0) * 2);
            
            return baseRadius * pulseFactor;
          },
          stroked: true,
          getLineColor: [255, 255, 255],
          lineWidthMinPixels: 2,
          pickable: true,
          onHover: (info) => setHoveredEvent(info.object || null)
        })
      );
    }

    // 2. Affected Roads (GeoJSON)
    if (affectedRoads && events.length > 0) {
      arr.push(
        new GeoJsonLayer({
          id: 'affected-roads-layer',
          data: affectedRoads,
          stroked: true,
          filled: false,
          lineWidthMinPixels: 2,
          getLineColor: (f: any) => {
            const baseColor = f.properties.color || [180, 0, 0, 220];
            const eventHour = f.properties.eventHour ?? timeOfDayHour;
            return getTimeDecayedColor(baseColor, eventHour, timeOfDayHour);
          },
          getLineWidth: (f: any) => {
            const eventHour = f.properties.eventHour ?? timeOfDayHour;
            return getTimeDecayedWidth(10, eventHour, timeOfDayHour);
          },
          pickable: true,
          updateTriggers: {
            getLineColor: [timeOfDayHour],
            getLineWidth: [timeOfDayHour]
          },
          transitions: {
            getLineColor: 500,
            getLineWidth: 500
          }
        })
      );
    }

    // 3. Spillover Roads (Purple)
    if (spilloverRoads && events.length > 0) {
      arr.push(
        new GeoJsonLayer({
          id: 'spillover-roads-layer',
          data: spilloverRoads,
          stroked: true,
          filled: false,
          lineWidthMinPixels: 2,
          getLineColor: (f: any) => {
            const baseColor = f.properties.color || [160, 32, 240, 220];
            const eventHour = f.properties.eventHour ?? timeOfDayHour;
            return getTimeDecayedColor(baseColor, eventHour, timeOfDayHour);
          },
          getLineWidth: (f: any) => {
            const eventHour = f.properties.eventHour ?? timeOfDayHour;
            return getTimeDecayedWidth(8, eventHour, timeOfDayHour);
          },
          pickable: true,
          updateTriggers: {
            getLineColor: [timeOfDayHour],
            getLineWidth: [timeOfDayHour]
          },
          transitions: {
            getLineColor: 500,
            getLineWidth: 500
          }
        })
      );
    }

    // 4. Detour Routes (Green)
    if (detourRoutes && events.length > 0) {
      arr.push(
        new GeoJsonLayer({
          id: 'detour-routes-layer',
          data: detourRoutes,
          stroked: true,
          filled: false,
          lineWidthMinPixels: 3,
          getLineColor: (f: any) => f.properties.color || [0, 255, 127, 255],
          getLineWidth: (f: any) => f.properties.isGreenWave ? 12 : 6,
          pickable: true
        })
      );
    }

    return arr;
  }, [events, riskScore, actions, timeOfDayHour, affectedRoads, spilloverRoads, detourRoutes, pulseFactor, roadNetwork]);

  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);

  return (
    <div className="absolute inset-0 w-full h-full bg-[var(--background)]">
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState }) => setViewState(viewState as any)}
        controller={true}
        layers={layers}
        onClick={handleMapClick}
        getCursor={({ isDragging }) => (isDragging ? 'grabbing' : isSimulating ? 'wait' : 'crosshair')}
      >
        <MapGL mapStyle={BASEMAP_STYLE} />
      </DeckGL>
      
      {/* Tooltip */}
      {hoveredEvent && (
        <div 
          className="absolute pointer-events-none bg-black/80 border border-gray-700 text-white p-3 rounded-lg shadow-xl backdrop-blur-sm z-50 transform -translate-x-1/2 -translate-y-[120%]"
          style={{ left: '50%', top: '50%' }}
        >
          <div className="font-bold text-[var(--color-brand-400)]">{hoveredEvent.cause}</div>
          <div className="text-xs text-gray-300 mt-1">Placed at: {hoveredEvent.timeHour}:00</div>
        </div>
      )}
    </div>
  );
}
