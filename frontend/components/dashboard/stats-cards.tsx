import React from "react";
import { GitPullRequest, Brain, ShieldAlert, CheckCircle2, FolderGit2 } from "lucide-react";
import { DashboardOverviewStats } from "@/lib/types";

interface Props {
  stats: DashboardOverviewStats;
}

export function StatsCards({ stats }: Props) {
  const criticalCount = stats.findings_by_severity?.critical || 0;
  const highCount = stats.findings_by_severity?.high || 0;
  const acceptanceRate = stats.feedback_metrics?.acceptance_rate ?? 0;
  const acceptedTotal = stats.feedback_metrics?.by_outcome?.accepted ?? 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Monitored Repos & PRs */}
      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur transition hover:border-slate-700">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Repositories Monitored</span>
          <FolderGit2 className="w-4 h-4 text-blue-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <div className="text-2xl font-bold text-white font-mono">{stats.total_repositories}</div>
          <span className="text-xs text-slate-500 font-mono">repos</span>
        </div>
        <div className="mt-2 text-xs text-slate-400 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
          <span>{stats.total_reviews} reviews executed</span>
        </div>
      </div>

      {/* 2. Recalled Memories */}
      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur transition hover:border-slate-700">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Hindsight Memories</span>
          <Brain className="w-4 h-4 text-purple-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <div className="text-2xl font-bold text-white font-mono">{stats.total_memories_recalled}</div>
          <span className="text-xs text-purple-400/80 font-mono">recalled</span>
        </div>
        <div className="mt-2 text-xs text-slate-400 flex items-center justify-between">
          <span>Persistent Team Rules</span>
          <span className="font-mono text-purple-300 text-[11px] bg-purple-950/60 px-1.5 py-0.5 rounded border border-purple-800/40">
            Tenant Isolated
          </span>
        </div>
      </div>

      {/* 3. Findings Detected */}
      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur transition hover:border-slate-700">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Findings Detected</span>
          <ShieldAlert className="w-4 h-4 text-amber-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <div className="text-2xl font-bold text-white font-mono">{stats.total_findings}</div>
          <span className="text-xs text-slate-500 font-mono">issues</span>
        </div>
        <div className="mt-2 flex items-center gap-2 text-xs">
          {criticalCount > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800/60 font-mono text-[11px]">
              {criticalCount} critical
            </span>
          )}
          {highCount > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-orange-950/80 text-orange-300 border border-orange-800/60 font-mono text-[11px]">
              {highCount} high
            </span>
          )}
          {criticalCount === 0 && highCount === 0 && (
            <span className="text-slate-500">All checks passed</span>
          )}
        </div>
      </div>

      {/* 4. Feedback Acceptance Rate */}
      <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur transition hover:border-slate-700">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span className="text-xs font-medium uppercase tracking-wider">Feedback Acceptance</span>
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <div className="text-2xl font-bold text-emerald-400 font-mono">
            {acceptanceRate > 0 ? `${acceptanceRate}%` : "100%"}
          </div>
          <span className="text-xs text-slate-500 font-mono">accepted</span>
        </div>
        <div className="mt-2 text-xs text-slate-400 flex items-center justify-between">
          <span>{acceptedTotal} accepted suggestions</span>
          {stats.avg_duration_ms && (
            <span className="text-slate-500 font-mono text-[11px]">
              ~{Math.round(stats.avg_duration_ms)}ms/rev
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
