import type {
  BatchStatus,
  BenchmarkConfig,
  BenchmarkMetrics,
  ReviewableEmail,
  ReviewAction,
  ReviewActionType,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Body wasn't JSON; fall back to statusText already set above.
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export function getEmails(): Promise<ReviewableEmail[]> {
  return apiFetch<ReviewableEmail[]>("/api/emails");
}

export function submitReview(
  emailId: number,
  action: ReviewActionType,
  editedReply?: string
): Promise<ReviewAction> {
  return apiFetch<ReviewAction>(`/api/emails/${emailId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action,
      edited_reply: action === "edit" ? editedReply : undefined,
    }),
  });
}

export function getBatches(): Promise<BatchStatus[]> {
  return apiFetch<BatchStatus[]>("/api/batches");
}

export function getBenchmarkConfig(): Promise<BenchmarkConfig> {
  return apiFetch<BenchmarkConfig>("/api/benchmark/config");
}

export interface BenchmarkStartConfig {
  model: string;
  temperature: number;
}

export function startBenchmark(
  configs: BenchmarkStartConfig[],
  runsPerPrompt: number
): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/api/benchmark/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ configs, runs_per_prompt: runsPerPrompt }),
  });
}

export function getBenchmarkStatus(): Promise<{ benchmark_running: boolean }> {
  return apiFetch<{ benchmark_running: boolean }>("/api/benchmark/status");
}

export function getBenchmarkMetrics(): Promise<BenchmarkMetrics> {
  return apiFetch<BenchmarkMetrics>("/api/benchmark/metrics");
}
