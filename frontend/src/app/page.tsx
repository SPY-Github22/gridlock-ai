'use client';
import dynamic from 'next/dynamic';
import { ErrorBoundary } from '../components/ErrorBoundary';

// DeckGL needs to be client-side rendered only to avoid hydration mismatch with WebGL
const Map = dynamic(() => import('../components/Map'), { 
  ssr: false,
  loading: () => (
    <div className="flex h-screen w-full items-center justify-center bg-[var(--background)]">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-gray-800 border-t-[var(--color-brand-600)] rounded-full animate-spin"></div>
        <p className="text-gray-400 font-medium tracking-widest uppercase text-sm">Initializing Spatial Engine...</p>
      </div>
    </div>
  )
});

const SimulatorHUD = dynamic(() => import('../components/SimulatorHUD'), { ssr: false });

export default function Home() {
  return (
    <main className="relative w-full h-screen overflow-hidden bg-[var(--background)]">
      <ErrorBoundary>
        <Map />
        <SimulatorHUD />
      </ErrorBoundary>
    </main>
  );
}
