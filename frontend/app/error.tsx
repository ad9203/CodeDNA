"use client";

import { useEffect } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Dashboard error caught by route boundary:", error);
  }, [error]);

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 text-slate-100">
      <div className="max-w-md w-full border border-slate-800 bg-slate-900/60 p-8 rounded-xl shadow-2xl backdrop-blur text-center space-y-4">
        <div className="inline-flex p-3 rounded-full bg-rose-950/80 text-rose-400 border border-rose-800/80 mb-2">
          <AlertCircle className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-semibold tracking-tight">Dashboard Unavailable</h2>
        <p className="text-sm text-slate-400 font-mono text-left bg-slate-950 p-3 rounded border border-slate-800 overflow-x-auto">
          {error.message || "Failed to load CodeDNA dashboard state."}
        </p>
        <button
          onClick={() => reset()}
          className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 font-medium text-sm text-white transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Retry Connection
        </button>
      </div>
    </div>
  );
}
