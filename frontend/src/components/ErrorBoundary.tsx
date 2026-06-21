'use client';
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-[var(--background)] text-[var(--foreground)] p-8">
          <div className="glass-panel p-8 rounded-xl max-w-lg w-full text-center">
            <h2 className="text-2xl font-bold text-red-400 mb-4">UI Rendering Error</h2>
            <p className="text-gray-300 mb-6">
              The 3D geospatial map failed to initialize. This could be due to WebGL not being supported in this browser.
            </p>
            <div className="bg-black/50 p-4 rounded text-left overflow-auto text-sm font-mono text-red-300">
              {this.state.error?.toString()}
            </div>
            <button
              className="mt-6 px-6 py-2 bg-[var(--color-brand-600)] text-black font-semibold rounded hover:bg-[var(--color-brand-500)] transition-colors"
              onClick={() => window.location.reload()}
            >
              Reload Dashboard
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
