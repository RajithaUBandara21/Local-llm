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

export interface PageParams {
  limit?: number;
  offset?: number;
}

export function getEmails(
  batchId?: number,
  page?: PageParams
): Promise<ReviewableEmail[]> {
  const params = new URLSearchParams();
  if (batchId !== undefined) params.set("batch_id", String(batchId));
  if (page?.limit !== undefined) params.set("limit", String(page.limit));
  if (page?.offset !== undefined) params.set("offset", String(page.offset));
  const query = params.size > 0 ? `?${params.toString()}` : "";
  return apiFetch<ReviewableEmail[]>(`/api/emails${query}`);
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

export function getBatches(page?: PageParams): Promise<BatchStatus[]> {
  const params = new URLSearchParams();
  if (page?.limit !== undefined) params.set("limit", String(page.limit));
  if (page?.offset !== undefined) params.set("offset", String(page.offset));
  const query = params.size > 0 ? `?${params.toString()}` : "";
  return apiFetch<BatchStatus[]>(`/api/batches${query}`);
}

export function createBatch(
  file: string,
  receivedAfter?: string,
  receivedBefore?: string
): Promise<BatchStatus> {
  return apiFetch<BatchStatus>("/api/batches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file,
      received_after: receivedAfter || undefined,
      received_before: receivedBefore || undefined,
    }),
  });
}

export function stopBatch(batchId: number): Promise<BatchStatus> {
  return apiFetch<BatchStatus>(`/api/batches/${batchId}/stop`, {
    method: "POST",
  });
}

export function resumeBatch(
  batchId: number,
  receivedAfter?: string,
  receivedBefore?: string
): Promise<BatchStatus> {
  return apiFetch<BatchStatus>(`/api/batches/${batchId}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      received_after: receivedAfter || undefined,
      received_before: receivedBefore || undefined,
    }),
  });
}

export async function deleteBatch(batchId: number): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/batches/${batchId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText);
  }
}

export function uploadMailboxFile(
  file: File,
  name?: string
): Promise<{ file: string }> {
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);
  return apiFetch<{ file: string }>("/api/mailbox-files", {
    method: "POST",
    body: formData,
  });
}

export interface PendingMailboxFile {
  file: string;
  display_name: string;
  created_at: string;
}

export function getPendingMailboxFiles(): Promise<PendingMailboxFile[]> {
  return apiFetch<PendingMailboxFile[]>("/api/mailbox-files");
}

export async function discardPendingMailboxFile(file: string): Promise<void> {
  const response = await fetch(
    `${BASE_URL}/api/mailbox-files/${encodeURIComponent(file)}`,
    { method: "DELETE" }
  );
  if (!response.ok) {
    throw new ApiError(response.status, response.statusText);
  }
}

export function previewMailboxFile(
  file: string
): Promise<{ received_at: (string | null)[] }> {
  return apiFetch<{ received_at: (string | null)[] }>(
    `/api/mailbox-files/${encodeURIComponent(file)}/preview`
  );
}

export function previewPendingEmails(
  batchId: number
): Promise<{ received_at: (string | null)[] }> {
  return apiFetch<{ received_at: (string | null)[] }>(
    `/api/batches/${batchId}/pending-preview`
  );
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
