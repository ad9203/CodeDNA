"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught frontend error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-lg border border-rose-900/60 bg-rose-950/20 p-6 text-rose-200">
          <div className="flex items-center gap-3 mb-3">
            <AlertTriangle className="h-5 w-5 text-rose-400" />
            <h3 className="font-semibold text-rose-100">
              {this.props.fallbackTitle || "Something went wrong"}
            </h3>
          </div>
          <p className="text-sm text-rose-300/80 mb-4 font-mono">
            {this.state.error?.message || "An unexpected rendering error occurred"}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="inline-flex items-center gap-2 rounded-md bg-rose-900/40 px-3 py-1.5 text-xs font-medium text-rose-200 hover:bg-rose-900/70 border border-rose-800 transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
