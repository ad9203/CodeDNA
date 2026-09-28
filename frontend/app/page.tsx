import { Suspense } from "react";
import { Database, GitPullRequest, ShieldCheck, Cpu } from "lucide-react";

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-900/50 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20">
              DNA
            </div>
            <div>
              <span className="font-semibold tracking-tight text-white">CodeDNA</span>
              <span className="ml-2 text-xs text-slate-400 font-mono">v0.1.0-alpha</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/80 text-xs font-medium text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              Connected
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        {/* Hero Banner */}
        <div className="border border-slate-800 rounded-xl bg-gradient-to-r from-slate-900/90 to-slate-900/40 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-xl font-semibold text-white tracking-tight">
              Persistent Code Review Engine
            </h1>
            <p className="text-sm text-slate-400">
              Reviews pull requests using accumulated team conventions, past review approvals, and postmortem records.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs font-mono text-slate-400 bg-slate-950/80 px-3 py-2 rounded-lg border border-slate-800">
            <Cpu className="w-3.5 h-3.5 text-blue-400" />
            <span>Hindsight + Groq Powered</span>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl border border-slate-800/80 bg-slate-900/40">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-medium">PRs Monitored</span>
              <GitPullRequest className="w-4 h-4 text-blue-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono">0</div>
          </div>

          <div className="p-4 rounded-xl border border-slate-800/80 bg-slate-900/40">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-medium">Memories Recalled</span>
              <Database className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono">0</div>
          </div>

          <div className="p-4 rounded-xl border border-slate-800/80 bg-slate-900/40">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-medium">Findings Generated</span>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-white font-mono">0</div>
          </div>

          <div className="p-4 rounded-xl border border-slate-800/80 bg-slate-900/40">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-medium">Engine Mode</span>
              <Cpu className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-sm font-semibold text-emerald-400 font-mono mt-1">Active Memory</div>
          </div>
        </div>

        {/* Empty State Table Placeholder for Module 00 */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 overflow-hidden">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">Live Pull Request Reviews</h2>
            <span className="text-xs text-slate-400 font-mono">Ready for webhooks</span>
          </div>
          <div className="p-12 text-center text-slate-400 space-y-3">
            <GitPullRequest className="w-8 h-8 mx-auto text-slate-600" />
            <p className="text-sm">No pull request reviews recorded yet.</p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Configure your GitHub webhook or run the demo harness in Module 14 to see CodeDNA recall historical memory and analyze PR diffs.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
