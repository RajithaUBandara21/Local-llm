// Mirrors the fields of app/schemas.py that this UI consumes.

export type Category =
  | "refund"
  | "delivery"
  | "billing"
  | "complaint"
  | "inquiry"
  | "spam"
  | "other";

export type Priority = "urgent" | "high" | "normal" | "low";

export type Flag = "stale_context" | "out_of_policy";

export type TriageStatus = "ok" | "needs_review" | "failed";

export type ReviewActionType = "approve" | "edit" | "reject";

export interface TriageResult {
  category: Category;
  priority: Priority;
  summary: string;
  suggested_reply: string | null;
  confidence: number;
  flags: Flag[];
  flag_reason: string | null;
}

export interface TriageResponse {
  status: TriageStatus;
  model: string;
  attempts: number;
  latency_sec: number;
  result: TriageResult | null;
  failure_reason: string | null;
}

export interface ReviewAction {
  id: number;
  email_id: number;
  action: ReviewActionType;
  edited_reply: string | null;
  created_at: string;
}

export interface ReviewableEmail {
  id: number;
  sender: string;
  subject: string;
  body_clean: string;
  received_at: string | null;
  batch_id: number;
  triage: TriageResponse | null;
  review: ReviewAction | null;
}

export interface BatchStatus {
  id: number;
  source_file: string;
  status: "running" | "completed";
  active: boolean;
  total: number;
  processed: number;
  ok: number;
  needs_review: number;
  failed: number;
  created_at: string;
  finished_at: string | null;
}

// Client-only mock row for the bulk-insert test view (feature 22). Deliberately
// distinct from ReviewableEmail: it is never triaged or reviewed, never sent to
// the backend, and never persisted. Feature 25 owns the real bulk-insert shape.
export interface MockTestEmail {
  id: string;
  sender: string;
  subject: string;
  received_at: string;
}

export type GmailConnectionStatus = "disconnected" | "connected";

export interface GmailConnection {
  status: GmailConnectionStatus;
  connectedEmail: string | null;
  connectedAt: string | null;
}

// Benchmark testing screen (feature 24). Mirrors GET /api/benchmark/config.
export interface BenchmarkConfig {
  models: string[];
  temperatures: number[];
  default_runs_per_prompt: number;
  max_runs_per_prompt: number;
}

export type BenchmarkRunState = "idle" | "starting" | "running" | "error";

// One queued model/temperature row in the run-configuration panel.
export interface BenchmarkConfigRow {
  id: string;
  model: string;
  temperature: number;
}

// CSV rows come back as string-keyed string values (app/repositories, CSVMetricsRepository).
export interface BenchmarkMetrics {
  latest_benchmark_file: string;
  total_runs: number;
  data: Record<string, string>[];
}

// Per-model averages derived client-side from BenchmarkMetrics.data; the
// backend has no aggregation endpoint, so this is computed, not fetched.
export interface BenchmarkModelSummary {
  model: string;
  attempts: number;
  avgTtftSec: number;
  avgLatencySec: number;
  avgTokensPerSec: number;
  avgCpuPercent: number;
  avgRamMb: number;
  validJsonPercent: number;
}

// Placeholder triage-evaluation accuracy shown on the benchmark screen until
// feature 27 provides real numbers. Client-only; never sent to the backend.
export interface MockAccuracySummary {
  model: string;
  accuracyPercent: number;
  sampleSize: number;
}

// Placeholder Q4-vs-Q5 model-comparison rows shown on the benchmark screen
// until feature 28 provides real numbers. Client-only; never sent to the backend.
export interface MockModelComparisonRow {
  metric: string;
  q4Value: string;
  q5Value: string;
}
