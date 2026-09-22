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

export interface Agent {
  id: string;
  name: string;
}

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
  agent_id: string;
  action: ReviewActionType;
  edited_reply: string | null;
  created_at: string;
}

export interface MailboxEmail {
  id: number;
  sender: string;
  subject: string;
  body_clean: string;
  received_at: string | null;
  mailbox: string | null;
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
