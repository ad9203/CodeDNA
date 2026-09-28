import React from "react";
import { CheckCircle2, AlertTriangle, XCircle, Clock, Loader2 } from "lucide-react";
import { ReviewStatus } from "@/lib/types";

interface Props {
  status: ReviewStatus;
  className?: string;
}

export function PRStatusBadge({ status, className = "" }: Props) {
  switch (status) {
    case "reviewed":
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950/70 text-emerald-400 border border-emerald-800/80 ${className}`}
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          Reviewed
        </span>
      );
    case "degraded":
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-950/70 text-purple-300 border border-purple-800/80 ${className}`}
          title="Reviewed in stateless mode due to temporary Hindsight outage"
        >
          <AlertTriangle className="w-3.5 h-3.5 text-purple-400" />
          Degraded (Stateless)
        </span>
      );
    case "failed":
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-950/70 text-rose-300 border border-rose-800/80 ${className}`}
        >
          <XCircle className="w-3.5 h-3.5" />
          Failed
        </span>
      );
    case "processing":
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-950/70 text-blue-300 border border-blue-800/80 animate-pulse ${className}`}
        >
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          Reviewing...
        </span>
      );
    case "pending":
    default:
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-950/70 text-amber-300 border border-amber-800/80 ${className}`}
        >
          <Clock className="w-3.5 h-3.5" />
          Pending
        </span>
      );
  }
}
