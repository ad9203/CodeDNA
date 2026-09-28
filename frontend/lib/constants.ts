export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export const STATUS_COLORS = {
  pending: "bg-amber-900/40 text-amber-300 border-amber-800",
  processing: "bg-blue-900/40 text-blue-300 border-blue-800 animate-pulse",
  reviewed: "bg-emerald-900/40 text-emerald-300 border-emerald-800",
  degraded: "bg-purple-900/40 text-purple-300 border-purple-800",
  failed: "bg-rose-900/40 text-rose-300 border-rose-800",
} as const;

export const SEVERITY_COLORS = {
  critical: "bg-rose-950 text-rose-300 border-rose-800",
  high: "bg-orange-950 text-orange-300 border-orange-800",
  medium: "bg-amber-950 text-amber-300 border-amber-800",
  low: "bg-blue-950 text-blue-300 border-blue-800",
  info: "bg-slate-900 text-slate-300 border-slate-700",
} as const;
