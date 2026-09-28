"use client";

import React, { useState } from "react";
import {
  GitPullRequest,
  Search,
  Filter,
  Brain,
  ShieldCheck,
  Clock,
  ExternalLink,
  ChevronRight,
  FolderGit2,
} from "lucide-react";
import { ReviewRunListItem, RepositoryListItem } from "@/lib/types";
import { PRStatusBadge } from "./pr-status-badge";

interface Props {
  reviews: ReviewRunListItem[];
  repositories: RepositoryListItem[];
  onSelectReview: (reviewId: string) => void;
  selectedRepoId: string | null;
  onRepoChange: (repoId: string | null) => void;
  selectedStatus: string | null;
  onStatusChange: (status: string | null) => void;
}

export function PRTable({
  reviews,
  repositories,
  onSelectReview,
  selectedRepoId,
  onRepoChange,
  selectedStatus,
  onStatusChange,
}: Props) {
  const [searchTerm, setSearchTerm] = useState("");

  const filtered = reviews.filter((r) => {
    const matchesSearch =
      r.pr_title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.pr_author.toLowerCase().includes(searchTerm.toLowerCase()) ||
      r.repository_name.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesRepo = !selectedRepoId || r.repository_id === selectedRepoId;
    const matchesStatus = !selectedStatus || r.status === selectedStatus;

    return matchesSearch && matchesRepo && matchesStatus;
  });

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 backdrop-blur overflow-hidden shadow-xl">
      {/* Table Header & Controls */}
      <div className="p-4 border-b border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-950/40">
        <div className="flex items-center gap-2">
          <GitPullRequest className="w-5 h-5 text-blue-400" />
          <h2 className="text-sm font-semibold text-white">Live Pull Request Reviews</h2>
          <span className="text-xs font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full">
            {filtered.length} of {reviews.length}
          </span>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Search bar */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search PR, author, repo..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-blue-500 w-48 sm:w-60"
            />
          </div>

          {/* Repo selector */}
          <div className="flex items-center gap-1.5 bg-slate-950 px-2.5 py-1.5 rounded-lg border border-slate-800 text-xs text-slate-300">
            <FolderGit2 className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedRepoId || ""}
              onChange={(e) => onRepoChange(e.target.value ? e.target.value : null)}
              className="bg-transparent text-xs text-slate-200 focus:outline-none cursor-pointer"
            >
              <option value="" className="bg-slate-900 text-slate-200">
                All Repositories
              </option>
              {repositories.map((repo) => (
                <option key={repo.id} value={repo.id} className="bg-slate-900 text-slate-200">
                  {repo.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status buttons */}
          <div className="flex items-center bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-xs font-medium">
            <button
              onClick={() => onStatusChange(null)}
              className={`px-2.5 py-1 rounded-md transition ${
                !selectedStatus
                  ? "bg-slate-800 text-white shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              All
            </button>
            <button
              onClick={() => onStatusChange("reviewed")}
              className={`px-2.5 py-1 rounded-md transition ${
                selectedStatus === "reviewed"
                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800/80 shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Reviewed
            </button>
            <button
              onClick={() => onStatusChange("degraded")}
              className={`px-2.5 py-1 rounded-md transition ${
                selectedStatus === "degraded"
                  ? "bg-purple-950 text-purple-300 border border-purple-800/80 shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Degraded
            </button>
            <button
              onClick={() => onStatusChange("failed")}
              className={`px-2.5 py-1 rounded-md transition ${
                selectedStatus === "failed"
                  ? "bg-rose-950 text-rose-300 border border-rose-800/80 shadow"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Failed
            </button>
          </div>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase tracking-wider font-mono text-[11px]">
              <th className="py-3 px-4">Pull Request</th>
              <th className="py-3 px-4">Repository</th>
              <th className="py-3 px-4">Author</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Findings</th>
              <th className="py-3 px-4">Hindsight Memory</th>
              <th className="py-3 px-4">Duration</th>
              <th className="py-3 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-slate-500">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-slate-400">No pull request reviews found</p>
                    <p className="text-xs text-slate-600">
                      Try clearing filters or triggering a new PR webhook.
                    </p>
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => onSelectReview(r.id)}
                  className="hover:bg-slate-800/40 transition cursor-pointer group"
                >
                  {/* PR Title & Number */}
                  <td className="py-3.5 px-4 max-w-xs sm:max-w-md">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-blue-400 font-semibold">
                          #{r.pr_number}
                        </span>
                        <span className="font-medium text-slate-200 group-hover:text-blue-300 transition truncate">
                          {r.pr_title}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-[11px] font-mono text-slate-500">
                        <span>commit: {r.head_sha.slice(0, 7)}</span>
                        {r.pr_html_url && (
                          <a
                            href={r.pr_html_url}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="text-slate-500 hover:text-slate-300"
                          >
                            <ExternalLink className="w-3 h-3 inline" />
                          </a>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Repository */}
                  <td className="py-3.5 px-4 font-mono text-slate-400">
                    <span className="bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                      {r.repository_name}
                    </span>
                  </td>

                  {/* Author */}
                  <td className="py-3.5 px-4 text-slate-300 font-mono">
                    <span className="flex items-center gap-1.5">
                      <span className="h-5 w-5 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center text-[10px] uppercase font-bold">
                        {r.pr_author.slice(0, 2)}
                      </span>
                      <span>{r.pr_author}</span>
                    </span>
                  </td>

                  {/* Status */}
                  <td className="py-3.5 px-4">
                    <PRStatusBadge status={r.status} />
                  </td>

                  {/* Findings */}
                  <td className="py-3.5 px-4">
                    {r.finding_count > 0 ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-950/60 border border-amber-800/80 text-amber-300 font-mono font-medium">
                        <ShieldCheck className="w-3 h-3 text-amber-400" />
                        {r.finding_count} {r.finding_count === 1 ? "finding" : "findings"}
                      </span>
                    ) : (
                      <span className="text-slate-500 font-mono">Clean</span>
                    )}
                  </td>

                  {/* Hindsight Memory */}
                  <td className="py-3.5 px-4">
                    {r.memory_recalled_count > 0 ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-950/60 border border-purple-800/80 text-purple-300 font-mono font-medium">
                        <Brain className="w-3 h-3 text-purple-400" />
                        {r.memory_recalled_count} {r.memory_recalled_count === 1 ? "memory recalled" : "memories recalled"}
                      </span>
                    ) : (
                      <span className="text-slate-500 font-mono italic">None</span>
                    )}
                  </td>

                  {/* Duration */}
                  <td className="py-3.5 px-4 font-mono text-slate-400">
                    {r.total_duration_ms ? (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-600" />
                        <span>{r.total_duration_ms}ms</span>
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>

                  {/* Action */}
                  <td className="py-3.5 px-4 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectReview(r.id);
                      }}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-200 hover:bg-blue-600 hover:text-white transition shadow"
                    >
                      <span>Inspect</span>
                      <ChevronRight className="w-3 h-3" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
