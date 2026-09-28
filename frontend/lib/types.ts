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

export interface RepositoryListItem {
  id: string;
  owner: string;
  name: string;
  full_name: string;
  default_branch: string;
  pr_count: number;
  review_count: number;
  created_at: string;
  last_active_at: string | null;
}

export interface ReviewRunListItem {
  id: string;
  delivery_id: string;
  status: ReviewStatus;
  started_at: string;
  completed_at: string | null;
  total_duration_ms: number | null;
  finding_count: number;
  memory_recalled_count: number;
  repository_id: string;
  repository_name: string;
  pr_number: number;
  pr_title: string;
  pr_author: string;
  pr_html_url: string;
  head_sha: string;
}

export interface ReviewRunListResponse {
  items: ReviewRunListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReviewFindingDetail {
  id: string;
  review_run_id: string;
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
  feedback_status: string | null;
}

export interface MemoryAuditDetail {
  id: string;
  review_run_id: string;
  memory_source_id: string | null;
  memory_type: string | null;
  memory_text_sanitized: string;
  relevance_score: number | null;
  rank_order: number;
  recall_timestamp: string;
}

export interface ReviewRunDetailResponse {
  id: string;
  delivery_id: string;
  status: ReviewStatus;
  started_at: string;
  completed_at: string | null;
  total_duration_ms: number | null;
  finding_count: number;
  memory_recalled_count: number;
  error_code: string | null;
  error_message_safe: string | null;
  repository: {
    id: string;
    owner: string;
    name: string;
    full_name: string;
    default_branch: string;
  };
  pull_request: {
    id: string;
    pr_number: number;
    title: string;
    author_login: string;
    head_sha: string;
    base_sha: string;
    html_url: string;
  };
  findings: ReviewFindingDetail[];
  memories: MemoryAuditDetail[];
  feedback_count: number;
}

export interface DashboardOverviewStats {
  total_repositories: number;
  total_reviews: number;
  total_findings: number;
  total_memories_recalled: number;
  findings_by_severity: Record<string, number>;
  feedback_metrics: {
    total: number;
    by_outcome: Record<string, number>;
    acceptance_rate: number;
  };
  avg_duration_ms: number | null;
}

export interface FindingFeedbackRequest {
  outcome: "accepted" | "rejected" | "modified" | "ignored";
  feedback_text: string;
  actor_login?: string;
  source_url?: string;
}

export interface ReviewFeedbackResponse {
  id: string;
  review_run_id: string;
  finding_id: string | null;
  actor_login: string;
  outcome: string;
  feedback_text: string;
  source_url: string | null;
  created_at: string;
  retained_in_hindsight: boolean;
  message: string;
}
