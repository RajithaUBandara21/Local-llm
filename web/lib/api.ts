import type {
  Agent,
  BatchStatus,
  MailboxEmail,
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

export function getAgents(): Promise<Agent[]> {
  return apiFetch<Agent[]>("/api/agents");
}

export function getMailboxes(agentId: string): Promise<string[]> {
  return apiFetch<string[]>("/api/mailboxes", {
    headers: { "X-Agent-Id": agentId },
  });
}

export function getMailboxEmails(
  agentId: string,
  mailbox: string
): Promise<MailboxEmail[]> {
  return apiFetch<MailboxEmail[]>(
    `/api/mailboxes/${encodeURIComponent(mailbox)}/emails`,
    { headers: { "X-Agent-Id": agentId } }
  );
}

export function submitReview(
  agentId: string,
  mailbox: string,
  emailId: number,
  action: ReviewActionType,
  editedReply?: string
): Promise<ReviewAction> {
  return apiFetch<ReviewAction>(
    `/api/mailboxes/${encodeURIComponent(mailbox)}/emails/${emailId}/review`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Agent-Id": agentId,
      },
      body: JSON.stringify({
        action,
        edited_reply: action === "edit" ? editedReply : undefined,
      }),
    }
  );
}

export function getBatches(): Promise<BatchStatus[]> {
  return apiFetch<BatchStatus[]>("/api/batches");
}
