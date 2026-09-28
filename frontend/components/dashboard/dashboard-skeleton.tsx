import React from "react";

export function DashboardSkeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      {/* Stats Grid Skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
            <div className="h-3 w-28 bg-slate-800 rounded"></div>
            <div className="h-7 w-16 bg-slate-800 rounded"></div>
            <div className="h-2 w-36 bg-slate-800 rounded"></div>
          </div>
        ))}
      </div>

      {/* Table Skeleton */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/40 overflow-hidden space-y-4 p-6">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="h-5 w-48 bg-slate-800 rounded"></div>
          <div className="h-8 w-64 bg-slate-800 rounded"></div>
        </div>

        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-center justify-between py-3 border-b border-slate-800/40">
            <div className="space-y-2">
              <div className="h-4 w-72 bg-slate-800 rounded"></div>
              <div className="h-2 w-32 bg-slate-800 rounded"></div>
            </div>
            <div className="h-6 w-20 bg-slate-800 rounded-full"></div>
            <div className="h-6 w-24 bg-slate-800 rounded-full"></div>
            <div className="h-6 w-16 bg-slate-800 rounded"></div>
          </div>
        ))}
      </div>
    </div>
  );
}
