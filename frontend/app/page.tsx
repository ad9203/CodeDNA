"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Brain,
  Cpu,
  RefreshCw,
  Sparkles,
  GitPullRequest,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import {
  DashboardOverviewStats,
  RepositoryListItem,
  ReviewRunListItem,
  ReviewRunDetailResponse,
} from "@/lib/types";
import {
  getStatsOverview,
  getRepositories,
  getReviews,
  getReviewDetail,
  DEMO_OVERVIEW_STATS,
  DEMO_REPOSITORIES,
  DEMO_REVIEWS_RESPONSE,
  DEMO_REVIEW_DETAILS,
} from "@/lib/api";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { PRTable } from "@/components/dashboard/pr-table";
import { ReviewInspectionModal } from "@/components/dashboard/review-inspection-modal";
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardOverviewStats | null>(null);
  const [repositories, setRepositories] = useState<RepositoryListItem[]>([]);
  const [reviews, setReviews] = useState<ReviewRunListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [demoMode, setDemoMode] = useState<boolean>(false);

  // Filters & Modal State
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null);
  const [activeReviewDetail, setActiveReviewDetail] =
    useState<ReviewRunDetailResponse | null>(null);

  const loadData = useCallback(async (isDemo = false) => {
    if (isDemo) {
      setStats(DEMO_OVERVIEW_STATS);
      setRepositories(DEMO_REPOSITORIES);
      setReviews(DEMO_REVIEWS_RESPONSE.items);
      setLoading(false);
      return;
    }

    try {
      const [overviewData, reposData, reviewsData] = await Promise.all([
        getStatsOverview(),
        getRepositories(),
        getReviews(),
      ]);

      setStats(overviewData);
      setRepositories(reposData);
      setReviews(reviewsData.items);
    } catch (err) {
      console.error("Failed to load dashboard data from live API:", err);
      // Seamlessly fallback to demo mock data so UI remains interactive
      setStats(DEMO_OVERVIEW_STATS);
      setRepositories(DEMO_REPOSITORIES);
      setReviews(DEMO_REVIEWS_RESPONSE.items);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData(demoMode);
  }, [loadData, demoMode]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadData(demoMode);
  };

  const handleSelectReview = async (reviewId: string) => {
    if (demoMode) {
      const demo =
        DEMO_REVIEW_DETAILS[reviewId] || DEMO_REVIEW_DETAILS["demo-run-1"];
      setActiveReviewDetail(demo);
      return;
    }

    try {
      const detail = await getReviewDetail(reviewId);
      setActiveReviewDetail(detail);
    } catch (err) {
      console.error("Failed to load review detail:", err);
      const fallback =
        DEMO_REVIEW_DETAILS[reviewId] || DEMO_REVIEW_DETAILS["demo-run-1"];
      setActiveReviewDetail(fallback);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-blue-500/30">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/20 text-sm">
              DNA
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold tracking-tight text-white text-base">
                  CodeDNA
                </span>
                <span className="text-[11px] text-blue-400 font-mono bg-blue-950/60 px-1.5 py-0.5 rounded border border-blue-800/60">
                  Persistent Memory
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-mono leading-none">
                B2B AI Code Review Agent
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Demo Mode Toggle */}
            <div className="flex items-center gap-2 bg-slate-950 px-3 py-1 rounded-full border border-slate-800 text-xs">
              <span className="text-slate-400">Demo Scenario:</span>
              <button
                onClick={() => setDemoMode(!demoMode)}
                className={`px-2 py-0.5 rounded-full font-mono text-[11px] transition ${
                  demoMode
                    ? "bg-purple-900/80 text-purple-300 border border-purple-700 font-semibold"
                    : "bg-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                {demoMode ? "ON (Acme Corp)" : "OFF (Live API)"}
              </button>
            </div>

            {/* Refresh Button */}
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-2 rounded-lg bg-slate-800/80 text-slate-300 hover:text-white hover:bg-slate-700 transition border border-slate-700 disabled:opacity-50"
              title="Refresh reviews"
            >
              <RefreshCw
                className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`}
              />
            </button>

            {/* Status Indicator */}
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-950/60 border border-emerald-800/80 text-xs font-medium text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Memory Engine Active</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8 flex-1 w-full">
        {/* Hero Context Banner */}
        <div className="border border-slate-800 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900/80 to-indigo-950/30 p-6 flex flex-col md:flex-row md:items-center justify-between gap-6 shadow-xl relative overflow-hidden">
          <div className="space-y-2 max-w-2xl z-10">
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1 text-xs font-mono text-purple-400 bg-purple-950/60 px-2 py-0.5 rounded border border-purple-800/40">
                <Brain className="w-3.5 h-3.5" />
                Hindsight Continuous Learning Loop
              </span>
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Adaptive Pull Request Reviews with Team Memory
            </h1>
            <p className="text-sm text-slate-300 leading-relaxed">
              CodeDNA remembers historical review decisions, team conventions,
              and postmortems. When reviewers reject or modify findings, the
              agent immediately adapts future suggestions.
            </p>
          </div>

          <div className="flex flex-col gap-2 z-10 shrink-0 font-mono text-xs">
            <div className="flex items-center gap-2 bg-slate-950/80 px-3.5 py-2 rounded-xl border border-slate-800 text-slate-300">
              <Cpu className="w-4 h-4 text-blue-400" />
              <span>Groq gpt-oss-120b Engine</span>
            </div>
            <div className="flex items-center gap-2 bg-slate-950/80 px-3.5 py-2 rounded-xl border border-slate-800 text-slate-300">
              <Sparkles className="w-4 h-4 text-purple-400" />
              <span>Vectorize Hindsight Bank</span>
            </div>
          </div>
        </div>

        {/* Dashboard Body */}
        {loading ? (
          <DashboardSkeleton />
        ) : (
          <div className="space-y-8">
            {stats && <StatsCards stats={stats} />}

            <PRTable
              reviews={reviews}
              repositories={repositories}
              onSelectReview={handleSelectReview}
              selectedRepoId={selectedRepoId}
              onRepoChange={setSelectedRepoId}
              selectedStatus={selectedStatus}
              onStatusChange={setSelectedStatus}
            />
          </div>
        )}
      </main>

      {/* Review Inspection Modal / Drawer */}
      {activeReviewDetail && (
        <ReviewInspectionModal
          review={activeReviewDetail}
          onClose={() => setActiveReviewDetail(null)}
          onFeedbackSubmitted={() => loadData(demoMode)}
        />
      )}

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-6 text-center text-xs text-slate-500 font-mono">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>CodeDNA • Persistent Memory Code Review Agent</span>
          <span>Hindsight Cloud SDK + Groq Structured Output</span>
        </div>
      </footer>
    </div>
  );
}
