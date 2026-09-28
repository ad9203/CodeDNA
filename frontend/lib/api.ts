import { API_BASE_URL } from "./constants";
import {
  DashboardOverviewStats,
  FindingFeedbackRequest,
  MemoryAuditDetail,
  RepositoryListItem,
  ReviewFeedbackResponse,
  ReviewFindingDetail,
  ReviewRunDetailResponse,
  ReviewRunListResponse,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });

    if (!res.ok) {
      throw new ApiError(res.status, `API call failed: ${res.status} ${res.statusText}`);
    }

    return (await res.json()) as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(500, err instanceof Error ? err.message : "Network error");
  }
}

// ==========================================
// Dashboard Read API Functions
// ==========================================

export async function getRepositories(): Promise<RepositoryListItem[]> {
  try {
    return await fetchJson<RepositoryListItem[]>("/repositories");
  } catch (err) {
    console.warn("Falling back to demo repositories:", err);
    return DEMO_REPOSITORIES;
  }
}

export async function getReviews(params?: {
  repository_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<ReviewRunListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.repository_id) searchParams.set("repository_id", params.repository_id);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.limit) searchParams.set("limit", params.limit.toString());
  if (params?.offset) searchParams.set("offset", params.offset.toString());

  const qs = searchParams.toString();
  const endpoint = `/reviews${qs ? `?${qs}` : ""}`;

  try {
    return await fetchJson<ReviewRunListResponse>(endpoint);
  } catch (err) {
    console.warn("Falling back to demo reviews:", err);
    return DEMO_REVIEWS_RESPONSE;
  }
}

export async function getReviewDetail(reviewId: string): Promise<ReviewRunDetailResponse> {
  try {
    return await fetchJson<ReviewRunDetailResponse>(`/reviews/${reviewId}`);
  } catch (err) {
    console.warn(`Falling back to demo detail for review ${reviewId}:`, err);
    const demo = DEMO_REVIEW_DETAILS[reviewId] || DEMO_REVIEW_DETAILS["demo-run-1"];
    return demo;
  }
}

export async function getReviewFindings(reviewId: string): Promise<ReviewFindingDetail[]> {
  try {
    return await fetchJson<ReviewFindingDetail[]>(`/reviews/${reviewId}/findings`);
  } catch (err) {
    console.warn("Falling back to demo findings:", err);
    const detail = await getReviewDetail(reviewId);
    return detail.findings;
  }
}

export async function getReviewMemory(reviewId: string): Promise<MemoryAuditDetail[]> {
  try {
    return await fetchJson<MemoryAuditDetail[]>(`/reviews/${reviewId}/memory`);
  } catch (err) {
    console.warn("Falling back to demo memory audits:", err);
    const detail = await getReviewDetail(reviewId);
    return detail.memories;
  }
}

export async function getStatsOverview(): Promise<DashboardOverviewStats> {
  try {
    return await fetchJson<DashboardOverviewStats>("/stats/overview");
  } catch (err) {
    console.warn("Falling back to demo overview stats:", err);
    return DEMO_OVERVIEW_STATS;
  }
}

export async function submitFindingFeedback(
  reviewId: string,
  findingId: string,
  payload: FindingFeedbackRequest
): Promise<ReviewFeedbackResponse> {
  try {
    return await fetchJson<ReviewFeedbackResponse>(
      `/reviews/${reviewId}/findings/${findingId}/feedback`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    );
  } catch (err) {
    console.warn("Simulating offline feedback submission:", err);
    return {
      id: `local-fb-${Date.now()}`,
      review_run_id: reviewId,
      finding_id: findingId,
      actor_login: payload.actor_login || "reviewer",
      outcome: payload.outcome,
      feedback_text: payload.feedback_text,
      source_url: payload.source_url || null,
      created_at: new Date().toISOString(),
      retained_in_hindsight: true,
      message: "Feedback recorded (Demo Mode: retained to simulated memory)",
    };
  }
}

// ==========================================
// Deterministic Demo Mock Data
// ==========================================

export const DEMO_REPOSITORIES: RepositoryListItem[] = [
  {
    id: "repo-1",
    owner: "acme-corp",
    name: "commerce-platform",
    full_name: "acme-corp/commerce-platform",
    default_branch: "main",
    pr_count: 14,
    review_count: 32,
    created_at: new Date(Date.now() - 30 * 86400000).toISOString(),
    last_active_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    id: "repo-2",
    owner: "acme-corp",
    name: "payment-gateway",
    full_name: "acme-corp/payment-gateway",
    default_branch: "main",
    pr_count: 8,
    review_count: 19,
    created_at: new Date(Date.now() - 45 * 86400000).toISOString(),
    last_active_at: new Date(Date.now() - 14400000).toISOString(),
  },
];

export const DEMO_REVIEWS_RESPONSE: ReviewRunListResponse = {
  items: [
    {
      id: "demo-run-1",
      delivery_id: "deliv-4819a-mock",
      status: "reviewed",
      started_at: new Date(Date.now() - 45 * 60000).toISOString(),
      completed_at: new Date(Date.now() - 44 * 60000).toISOString(),
      total_duration_ms: 1340,
      finding_count: 2,
      memory_recalled_count: 3,
      repository_id: "repo-1",
      repository_name: "acme-corp/commerce-platform",
      pr_number: 142,
      pr_title: "feat(checkout): add idempotent stripe payment token retry logic",
      pr_author: "sarah-dev",
      pr_html_url: "https://github.com/acme-corp/commerce-platform/pull/142",
      head_sha: "9f32b1a8c4",
    },
    {
      id: "demo-run-2",
      delivery_id: "deliv-8201b-mock",
      status: "reviewed",
      started_at: new Date(Date.now() - 3 * 3600000).toISOString(),
      completed_at: new Date(Date.now() - 3 * 3600000 + 120000).toISOString(),
      total_duration_ms: 980,
      finding_count: 1,
      memory_recalled_count: 2,
      repository_id: "repo-2",
      repository_name: "acme-corp/payment-gateway",
      pr_number: 89,
      pr_title: "refactor(auth): migrate jwt session tokens to sha256 encrypted cookies",
      pr_author: "alex-security",
      pr_html_url: "https://github.com/acme-corp/payment-gateway/pull/89",
      head_sha: "4a88ef10c2",
    },
    {
      id: "demo-run-3",
      delivery_id: "deliv-9012c-mock",
      status: "degraded",
      started_at: new Date(Date.now() - 6 * 3600000).toISOString(),
      completed_at: new Date(Date.now() - 6 * 3600000 + 90000).toISOString(),
      total_duration_ms: 1820,
      finding_count: 1,
      memory_recalled_count: 0,
      repository_id: "repo-1",
      repository_name: "acme-corp/commerce-platform",
      pr_number: 141,
      pr_title: "fix(cart): debounce price recalculation on quantity increment",
      pr_author: "junior-coder",
      pr_html_url: "https://github.com/acme-corp/commerce-platform/pull/141",
      head_sha: "7b10ac99df",
    },
  ],
  total: 3,
  limit: 50,
  offset: 0,
};

export const DEMO_REVIEW_DETAILS: Record<string, ReviewRunDetailResponse> = {
  "demo-run-1": {
    id: "demo-run-1",
    delivery_id: "deliv-4819a-mock",
    status: "reviewed",
    started_at: new Date(Date.now() - 45 * 60000).toISOString(),
    completed_at: new Date(Date.now() - 44 * 60000).toISOString(),
    total_duration_ms: 1340,
    finding_count: 2,
    memory_recalled_count: 3,
    error_code: null,
    error_message_safe: null,
    repository: {
      id: "repo-1",
      owner: "acme-corp",
      name: "commerce-platform",
      full_name: "acme-corp/commerce-platform",
      default_branch: "main",
    },
    pull_request: {
      id: "pr-142",
      pr_number: 142,
      title: "feat(checkout): add idempotent stripe payment token retry logic",
      author_login: "sarah-dev",
      head_sha: "9f32b1a8c4",
      base_sha: "00192ea1b7",
      html_url: "https://github.com/acme-corp/commerce-platform/pull/142",
    },
    findings: [
      {
        id: "finding-101",
        review_run_id: "demo-run-1",
        severity: "critical",
        category: "architecture",
        confidence: 0.96,
        path: "services/checkout_service.py",
        line: 48,
        side: "RIGHT",
        title: "Direct database write in checkout service layer",
        message:
          "Direct call to `db.session.add(payment_record)` violates team architecture conventions. Service layer must strictly delegate writes through `PaymentRepository` abstractions.",
        rationale:
          "Past postmortem incident INC-402 occurred due to bypassing repository unit-of-work abstractions.",
        suggestion: "await self.payment_repo.save_transaction(payment_record)",
        feedback_status: "accepted",
      },
      {
        id: "finding-102",
        review_run_id: "demo-run-1",
        severity: "high",
        category: "security",
        confidence: 0.91,
        path: "services/stripe_client.py",
        line: 112,
        side: "RIGHT",
        title: "Missing idempotency key in Stripe charge retry loop",
        message:
          "Network retries on `stripe.Charge.create` must supply `idempotency_key=charge_uuid` to prevent accidental double-billing customers.",
        rationale:
          "Team convention rule: All external billing mutations must include unique deterministic idempotency headers.",
        suggestion:
          "stripe.Charge.create(..., idempotency_key=f'charge_{order_id}_{attempt}')",
        feedback_status: null,
      },
    ],
    memories: [
      {
        id: "mem-1",
        review_run_id: "demo-run-1",
        memory_source_id: "hindsight-rule-881",
        memory_type: "team_rule",
        memory_text_sanitized:
          "Team Architecture Rule: All service layer database operations must occur through repository abstractions. Direct ORM session calls in service classes are strictly forbidden.",
        relevance_score: 0.94,
        rank_order: 0,
        recall_timestamp: new Date(Date.now() - 45 * 60000).toISOString(),
      },
      {
        id: "mem-2",
        review_run_id: "demo-run-1",
        memory_source_id: "hindsight-postmortem-402",
        memory_type: "review_decision",
        memory_text_sanitized:
          "Postmortem INC-402: Stripe charge operations must strictly attach deterministic idempotency keys before retrying on 5xx network timeout.",
        relevance_score: 0.91,
        rank_order: 1,
        recall_timestamp: new Date(Date.now() - 45 * 60000).toISOString(),
      },
      {
        id: "mem-3",
        review_run_id: "demo-run-1",
        memory_source_id: "hindsight-convention-12",
        memory_type: "applied_convention",
        memory_text_sanitized:
          "Convention: Exception handling on billing integrations must log external request IDs while masking PCI cardholder numbers.",
        relevance_score: 0.86,
        rank_order: 2,
        recall_timestamp: new Date(Date.now() - 45 * 60000).toISOString(),
      },
    ],
    feedback_count: 1,
  },
};

export const DEMO_OVERVIEW_STATS: DashboardOverviewStats = {
  total_repositories: 2,
  total_reviews: 51,
  total_findings: 68,
  total_memories_recalled: 142,
  findings_by_severity: {
    critical: 8,
    high: 24,
    medium: 28,
    low: 8,
  },
  feedback_metrics: {
    total: 36,
    by_outcome: {
      accepted: 32,
      rejected: 3,
      modified: 1,
    },
    acceptance_rate: 88.9,
  },
  avg_duration_ms: 1120.5,
};
