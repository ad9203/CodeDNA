import { API_BASE_URL } from "./constants";
import { ReviewRun, SystemStats, ReviewFinding, RecalledMemory } from "./types";

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

export async function getReviews(): Promise<ReviewRun[]> {
  return fetchJson<ReviewRun[]>("/reviews");
}

export async function getReview(id: string): Promise<ReviewRun> {
  return fetchJson<ReviewRun>(`/reviews/${id}`);
}

export async function getReviewFindings(id: string): Promise<ReviewFinding[]> {
  return fetchJson<ReviewFinding[]>(`/reviews/${id}/findings`);
}

export async function getReviewMemory(id: string): Promise<RecalledMemory[]> {
  return fetchJson<RecalledMemory[]>(`/reviews/${id}/memory`);
}

export async function getStatsOverview(): Promise<SystemStats> {
  return fetchJson<SystemStats>("/stats/overview");
}

export async function submitFindingFeedback(
  reviewRunId: string,
  findingId: string,
  outcome: "accepted" | "rejected" | "modified",
  feedbackText: string
): Promise<{ success: boolean; memory_retained: boolean }> {
  return fetchJson<{ success: boolean; memory_retained: boolean }>(
    `/reviews/${reviewRunId}/findings/${findingId}/feedback`,
    {
      method: "POST",
      body: JSON.stringify({ outcome, feedback_text: feedbackText }),
    }
  );
}
