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
  display_name: string;
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

// One mail set queued in the left-side list column: a user-given display name,
// the uploaded mailbox file's stored server name, and the batch it started
// once processed (if any).
export type MailSetStatus = "pending" | "running" | "paused" | "completed" | "failed";

export interface MailSet {
  id: string;
  name: string;
  file: string;
  status: MailSetStatus;
  batch: BatchStatus | null;
  error: string | null;
}

export type GmailConnectionStatus = "disconnected" | "connected";

export interface GmailConnection {
  status: GmailConnectionStatus;
  connectedEmail: string | null;
  connectedAt: string | null;
}

// Admin model settings panel. Mirrors GET /api/models (AvailableModelsResponse)
// and the AppState.active_model / active_temperature fields that /api/model/change
// and /api/settings/temperature mutate.
export interface AvailableModelsResponse {
  models: string[];
}

export interface ActiveModelSettings {
  active_model: string;
  active_temperature: number;
}
