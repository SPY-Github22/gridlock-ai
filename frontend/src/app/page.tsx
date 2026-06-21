'use client';
import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { ErrorBoundary } from '../components/ErrorBoundary';

// DeckGL must be client-side only to avoid WebGL hydration mismatches
const Map = dynamic(() => import('../components/Map'), {
  ssr: false,
  loading: () => <LoadingScreen message="Initializing Spatial Engine..." />,
});

const SimulatorHUD = dynamic(() => import('../components/SimulatorHUD'), { ssr: false });

// ---------------------------------------------------------------------------
// Loading screen shown while the map or backend is warming up
// ---------------------------------------------------------------------------
function LoadingScreen({ message }: { message: string }) {
  return (
    <div className="flex h-screen w-full items-center justify-center bg-[var(--background)]">
      <div className="flex flex-col items-center gap-6">
        {/* Animated radar ring */}
        <div className="relative w-20 h-20">
          <div className="absolute inset-0 rounded-full border-4 border-[var(--color-brand-600)] opacity-20 animate-ping" />
          <div className="absolute inset-2 rounded-full border-4 border-gray-800 border-t-[var(--color-brand-500)] animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-2 h-2 rounded-full bg-[var(--color-brand-500)]" />
          </div>
        </div>
        <div className="flex flex-col items-center gap-1">
          <p className="text-[var(--color-brand-400)] font-bold tracking-widest uppercase text-sm">
            Gridlock AI
          </p>
          <p className="text-gray-500 text-xs tracking-wider">{message}</p>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page — waits for backend to be ready before showing the UI
// ---------------------------------------------------------------------------
export default function Home() {
  const [backendReady, setBackendReady] = useState(false);
  const [statusMessage, setStatusMessage] = useState('Connecting to simulation engine...');

  useEffect(() => {
    let attempts = 0;
    const maxAttempts = 15; // 15 × 2s = 30 second max wait

    const check = async () => {
      attempts++;
      try {
        const res = await fetch('/api/', { method: 'GET' });
        if (res.ok) {
          setBackendReady(true);
          return;
        }
      } catch {
        // backend not yet reachable
      }

      if (attempts >= maxAttempts) {
        // Give up waiting and show the UI anyway — user can still try
        setBackendReady(true);
        return;
      }

      setStatusMessage(`Warming up backend... (${attempts}/${maxAttempts})`);
      setTimeout(check, 2000);
    };

    check();
  }, []);

  if (!backendReady) {
    return <LoadingScreen message={statusMessage} />;
  }

  return (
    <main className="relative w-full h-screen overflow-hidden bg-[var(--background)]">
      <ErrorBoundary>
        <Map />
        <SimulatorHUD />
      </ErrorBoundary>
    </main>
  );
}
