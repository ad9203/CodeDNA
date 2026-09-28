"use client";

import React, { useState } from "react";
import {
  X,
  Brain,
  ShieldCheck,
  CheckCircle,
  XCircle,
  Edit3,
  ExternalLink,
  Code2,
  Clock,
  Sparkles,
  GitBranch,
} from "lucide-react";
import {
  ReviewRunDetailResponse,
  ReviewFindingDetail,
  FindingFeedbackRequest,
} from "@/lib/types";
import { submitFindingFeedback } from "@/lib/api";
import { MemoryAuditPanel } from "./memory-audit-panel";
import { PRStatusBadge } from "./pr-status-badge";

interface Props {
  review: ReviewRunDetailResponse;
  onClose: () => void;
  onFeedbackSubmitted?: () => void;
}

export function ReviewInspectionModal({
  review,
  onClose,
  onFeedbackSubmitted,
}: Props) {
  const [activeTab, setActiveTab] = useState<"findings" | "memory">("findings");
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);
  const [feedbackNotes, setFeedbackNotes] = useState<Record<string, string>>({});
  const [customInputOpen, setCustomInputOpen] = useState<Record<string, boolean>>({});

  const handleFeedback = async (
    finding: ReviewFindingDetail,
    outcome: "accepted" | "rejected" | "modified"
  ) => {
    setSubmittingId(finding.id);
    const customReason = feedbackNotes[finding.id] || "";
    const defaultReason =
      outcome === "rejected"
        ? "Reviewer rejected: team convention doesn't require this or exempt in this file."
        : outcome === "accepted"
        ? "Reviewer accepted: team convention confirmed."
        : "Reviewer modified standard.";

    const payload: FindingFeedbackRequest = {
      outcome,
      feedback_text: customReason.trim() ? customReason.trim() : defaultReason,
      actor_login: "dashboard_reviewer",
    };

    try {
      const res = await submitFindingFeedback(review.id, finding.id, payload);
      finding.feedback_status = outcome;
      setFeedbackSuccess(
        `Feedback recorded for "${finding.title}"! ${
          res.retained_in_hindsight
            ? "New convention retained to Hindsight persistent memory."
            : ""
        }`
      );
      if (onFeedbackSubmitted) onFeedbackSubmitted();
    } catch (err) {
      console.error("Failed to submit feedback:", err);
    } finally {
      setSubmittingId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl max-h-[90vh] bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-slate-100">
        {/* Header */}
        <div className="p-6 border-b border-slate-800 flex items-start justify-between gap-4 bg-slate-950/60">
          <div className="space-y-1.5 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-blue-400 bg-blue-950/60 px-2 py-0.5 rounded border border-blue-800/40">
                {review.repository.full_name}
              </span>
              <span className="text-xs font-mono text-slate-400">
                PR #{review.pull_request.pr_number}
              </span>
              <PRStatusBadge status={review.status} />
            </div>

            <h2 className="text-lg font-bold text-white tracking-tight leading-snug">
              {review.pull_request.title}
            </h2>

            <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400 pt-0.5 font-mono">
              <div className="flex items-center gap-1">
                <span>Author:</span>
                <span className="text-slate-200">{review.pull_request.author_login}</span>
              </div>
              <div className="flex items-center gap-1">
                <span>Head:</span>
                <span className="text-slate-200">{review.pull_request.head_sha.slice(0, 8)}</span>
              </div>
              {review.total_duration_ms && (
                <div className="flex items-center gap-1">
                  <Clock className="w-3 h-3 text-slate-500" />
                  <span>{review.total_duration_ms}ms</span>
                </div>
              )}
              {review.pull_request.html_url && (
                <a
                  href={review.pull_request.html_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-blue-400 hover:text-blue-300"
                >
                  <span>GitHub PR</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Feedback Success Notification */}
        {feedbackSuccess && (
          <div className="px-6 py-2.5 bg-emerald-950/80 border-b border-emerald-800 text-xs text-emerald-300 flex items-center justify-between animate-in fade-in">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{feedbackSuccess}</span>
            </div>
            <button
              onClick={() => setFeedbackSuccess(null)}
              className="text-emerald-400 hover:text-emerald-200"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Tab Controls */}
        <div className="px-6 border-b border-slate-800 flex items-center gap-6 bg-slate-900/40">
          <button
            onClick={() => setActiveTab("findings")}
            className={`py-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
              activeTab === "findings"
                ? "border-blue-500 text-white"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>Findings ({review.findings.length})</span>
          </button>

          <button
            onClick={() => setActiveTab("memory")}
            className={`py-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
              activeTab === "memory"
                ? "border-purple-500 text-white"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Brain className="w-4 h-4" />
            <span>Hindsight Memory Audit ({review.memories.length})</span>
          </button>
        </div>

        {/* Tab Content Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-4">
          {activeTab === "findings" ? (
            review.findings.length === 0 ? (
              <div className="p-8 text-center text-slate-400 space-y-2 border border-dashed border-slate-800 rounded-xl">
                <ShieldCheck className="w-8 h-8 mx-auto text-emerald-400" />
                <p className="text-sm font-medium text-slate-200">
                  No issues or rule violations identified.
                </p>
                <p className="text-xs text-slate-500">
                  This pull request satisfies all accumulated conventions and standard best practices.
                </p>
              </div>
            ) : (
              review.findings.map((f, idx) => {
                const isSubmitting = submittingId === f.id;
                const isCustomOpen = !!customInputOpen[f.id];

                return (
                  <div
                    key={f.id || idx}
                    className="p-5 rounded-xl border border-slate-800 bg-slate-900/70 space-y-3 transition hover:border-slate-700"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase tracking-wider ${
                            f.severity === "critical"
                              ? "bg-rose-950 text-rose-300 border border-rose-800"
                              : f.severity === "high"
                              ? "bg-orange-950 text-orange-300 border border-orange-800"
                              : f.severity === "medium"
                              ? "bg-amber-950 text-amber-300 border border-amber-800"
                              : "bg-blue-950 text-blue-300 border border-blue-800"
                          }`}
                        >
                          {f.severity}
                        </span>
                        <span className="text-xs font-mono text-slate-400">
                          {f.category}
                        </span>
                        <span className="text-xs font-mono text-slate-500">
                          Confidence: {Math.round(f.confidence * 100)}%
                        </span>
                      </div>

                      <div className="text-xs font-mono text-slate-400 flex items-center gap-1.5 bg-slate-950/80 px-2 py-1 rounded border border-slate-800">
                        <Code2 className="w-3.5 h-3.5 text-blue-400" />
                        <span className="text-slate-200">{f.path}</span>
                        {f.line && <span className="text-blue-400">:{f.line}</span>}
                      </div>
                    </div>

                    <h3 className="text-base font-semibold text-white tracking-tight">
                      {f.title}
                    </h3>

                    <p className="text-sm text-slate-300 leading-relaxed font-sans">
                      {f.message}
                    </p>

                    {f.rationale && (
                      <div className="text-xs text-slate-400 bg-slate-950/40 p-2.5 rounded-lg border border-slate-800/60 font-sans italic">
                        <strong className="not-italic text-slate-300 font-semibold">
                          Architectural Rationale:{" "}
                        </strong>
                        {f.rationale}
                      </div>
                    )}

                    {f.suggestion && (
                      <div className="space-y-1">
                        <span className="text-xs font-mono text-emerald-400 flex items-center gap-1">
                          <span>Suggested Code Diff:</span>
                        </span>
                        <pre className="p-3 rounded-lg bg-slate-950 font-mono text-xs text-emerald-300 border border-emerald-950/60 overflow-x-auto">
                          <code>{f.suggestion}</code>
                        </pre>
                      </div>
                    )}

                    {/* Human Feedback Loop Actions */}
                    <div className="pt-2 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500 font-medium">
                          Reviewer Feedback:
                        </span>
                        {f.feedback_status ? (
                          <span className="px-2 py-0.5 rounded text-xs font-mono font-medium capitalize bg-slate-800 text-slate-300 border border-slate-700">
                            Marked as: {f.feedback_status}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-500 italic">Unrated</span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          disabled={isSubmitting}
                          onClick={() => handleFeedback(f, "accepted")}
                          className="px-2.5 py-1 rounded-lg text-xs font-medium bg-emerald-950/60 text-emerald-300 border border-emerald-800/60 hover:bg-emerald-900/60 transition flex items-center gap-1 disabled:opacity-50"
                          title="Confirm this finding as an accurate standard"
                        >
                          <CheckCircle className="w-3.5 h-3.5" />
                          <span>Accept Rule</span>
                        </button>

                        <button
                          disabled={isSubmitting}
                          onClick={() => handleFeedback(f, "rejected")}
                          className="px-2.5 py-1 rounded-lg text-xs font-medium bg-rose-950/60 text-rose-300 border border-rose-800/60 hover:bg-rose-900/60 transition flex items-center gap-1 disabled:opacity-50"
                          title="Reject this finding; synthesizes a negative constraint into Hindsight"
                        >
                          <XCircle className="w-3.5 h-3.5" />
                          <span>Reject (Don&apos;t Flag)</span>
                        </button>

                        <button
                          onClick={() =>
                            setCustomInputOpen({
                              ...customInputOpen,
                              [f.id]: !isCustomOpen,
                            })
                          }
                          className="px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 transition flex items-center gap-1"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                          <span>Add Note</span>
                        </button>
                      </div>
                    </div>

                    {isCustomOpen && (
                      <div className="mt-2 p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-2 animate-in fade-in">
                        <label className="text-xs text-slate-400 font-medium">
                          Explain team convention / reason for Hindsight memory:
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. Migration scripts are exempt from repository abstraction..."
                          value={feedbackNotes[f.id] || ""}
                          onChange={(e) =>
                            setFeedbackNotes({
                              ...feedbackNotes,
                              [f.id]: e.target.value,
                            })
                          }
                          className="w-full px-3 py-1.5 rounded bg-slate-900 border border-slate-800 text-xs text-slate-100 placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                        />
                      </div>
                    )}
                  </div>
                );
              })
            )
          ) : (
            <MemoryAuditPanel memories={review.memories} />
          )}
        </div>
      </div>
    </div>
  );
}
