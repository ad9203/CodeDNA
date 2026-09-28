export type ReviewStatus =
  | "pending"
  | "processing"
  | "reviewed"
  | "degraded"
  | "failed";

export type FindingSeverity = "critical" | "high" | "medium" | "low" | "info";

export type FindingCategory =
  | "correctness"
  | "security"
  | "performance"
  | "architecture"
  | "maintainability"
  | "testing"
  | "team_convention"
  | "other";

export interface ReviewFinding {
  id?: string;
  severity: FindingSeverity;
  category: FindingCategory;
  confidence: number;
  path: string;
  line: number | null;
  side: "RIGHT" | "LEFT" | null;
  title: string;
  message: string;
  rationale: string;
  suggestion: string | null;
  feedback_status?: string | null;
}

export interface RecalledMemory {
  id?: string;
  type?: string;
  text: string;
  relevance?: number | null;
  source?: string | null;
  tags?: string[];
}

export interface ReviewRun {
  id: string;
  repository: string;
  pr_number: number;
  pr_title: string;
  author_login: string;
  status: ReviewStatus;
  risk: "low" | "medium" | "high" | "critical";
  summary: string;
  findings_count: number;
  memory_recalled_count: number;
  duration_ms: number;
  degraded: boolean;
  html_url: string;
  created_at: string;
  findings?: ReviewFinding[];
  memories?: RecalledMemory[];
  team_conventions_applied?: string[];
  memory_influence_summary?: string[];
}

export interface SystemStats {
  prs_reviewed: number;
  reviews_processed: number;
  memory_recalls: number;
  findings_generated: number;
  degraded_runs: number;
  last_review_time: string | null;
}
