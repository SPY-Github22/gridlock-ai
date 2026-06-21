'use client';
import React, { useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { Map as MapGL } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { ScatterplotLayer, GeoJsonLayer } from '@deck.gl/layers';
import { useStore } from '../store/useStore';

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
      addEvent({
        id: Date.now(),
        lng: info.coordinate[0], 
        lat: info.coordinate[1],
        cause: eventCause,
        timeHour: timeOfDayHour
      });
    }
  };

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
            return [0, 240, 255, 200]; // Brand Neon Blue for Hazards
          },
          getRadius: (d) => {
            if (d.cause === 'Barricade' || d.cause === 'Police Squad') return 30;
            const baseRadius = riskScore > 0 ? 50 + (riskScore * 15) : 30;
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
            const baseColor = f.properties.color || [255, 50, 50, 220];
            // eventHour from properties; if missing, use current scrubber so lines are always visible
            const eventHour = f.properties.eventHour ?? timeOfDayHour;
            const timeDiff = Math.abs(timeOfDayHour - eventHour);
            // Only fade if scrubber is >8 hours away (much more forgiving)
            const decayFactor = Math.max(0.15, 1 - (timeDiff * 0.1));
            return [baseColor[0], baseColor[1], baseColor[2], Math.round((baseColor[3] ?? 220) * decayFactor)];
          },
          getLineWidth: (f: any) => {
            const eventHour = f.properties.eventHour ?? timeOfDayHour;
            const timeDiff = Math.abs(timeOfDayHour - eventHour);
            const decayFactor = Math.max(0.3, 1 - (timeDiff * 0.1));
            return 10 * decayFactor; // Wider lines so they are clearly visible
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
            const timeDiff = Math.abs(timeOfDayHour - eventHour);
            const decayFactor = Math.max(0.15, 1 - (timeDiff * 0.1));
            return [baseColor[0], baseColor[1], baseColor[2], Math.round((baseColor[3] ?? 220) * decayFactor)];
          },
          getLineWidth: (f: any) => {
            const eventHour = f.properties.eventHour ?? timeOfDayHour;
            const timeDiff = Math.abs(timeOfDayHour - eventHour);
            const decayFactor = Math.max(0.3, 1 - (timeDiff * 0.1));
            return 8 * decayFactor;
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
          getLineWidth: 6,
          pickable: true
        })
      );
    }

    return arr;
  }, [events, riskScore, actions, timeOfDayHour, affectedRoads, spilloverRoads, detourRoutes, pulseFactor]);

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
