import React from "react";
import { Brain, BookmarkCheck, AlertCircle, Sparkles } from "lucide-react";
import { MemoryAuditDetail } from "@/lib/types";

interface Props {
  memories: MemoryAuditDetail[];
  emptyMessage?: string;
}

export function MemoryAuditPanel({ memories, emptyMessage }: Props) {
  if (!memories || memories.length === 0) {
    return (
      <div className="p-8 text-center text-slate-400 space-y-3 border border-dashed border-slate-800 rounded-xl bg-slate-950/40">
        <Brain className="w-8 h-8 mx-auto text-slate-600" />
        <p className="text-sm font-medium">
          {emptyMessage || "No prior team memory was recalled for this review run."}
        </p>
        <p className="text-xs text-slate-500 max-w-md mx-auto">
          As human developers accept, reject, or modify review findings, CodeDNA automatically learns and recalls durable conventions for future pull requests.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {memories.map((m, idx) => {
        const relevancePercent = m.relevance_score
          ? Math.round(m.relevance_score * 100)
          : null;

        return (
          <div
            key={m.id || idx}
            className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 transition hover:border-slate-700 space-y-2"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="flex items-center justify-center h-6 w-6 rounded-md bg-purple-950/80 border border-purple-800/80 text-purple-400 font-mono text-xs">
                  #{idx + 1}
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono font-medium uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
                  {m.memory_type || "team_rule"}
                </span>
                {m.memory_source_id && (
                  <span className="text-[11px] font-mono text-slate-500 truncate max-w-[200px]">
                    id: {m.memory_source_id}
                  </span>
                )}
              </div>

              {relevancePercent !== null && (
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-indigo-400 rounded-full"
                      style={{ width: `${relevancePercent}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono font-semibold text-purple-300">
                    {relevancePercent}% match
                  </span>
                </div>
              )}
            </div>

            <p className="text-sm text-slate-200 leading-relaxed font-sans bg-slate-950/50 p-3 rounded-lg border border-slate-800/60">
              {m.memory_text_sanitized}
            </p>

            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
              <div className="flex items-center gap-1.5 text-purple-400/80 font-mono">
                <Sparkles className="w-3 h-3" />
                <span>Influenced Groq Structured Review Context</span>
              </div>
              <span className="font-mono">
                {new Date(m.recall_timestamp).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
