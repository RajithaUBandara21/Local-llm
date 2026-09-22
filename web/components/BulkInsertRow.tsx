import type { MockTestEmail } from "@/lib/types";

function formatReceived(receivedAt: string): string {
  const date = new Date(receivedAt);
  if (Number.isNaN(date.getTime())) return receivedAt;
  return date.toLocaleString();
}

// Mock rows are display-only: there is no triage result behind them, so
// unlike QueueRow they render as a plain row (not a button) with no
// selection or detail-panel wiring.
export function BulkInsertRow({ email }: Readonly<{ email: MockTestEmail }>) {
  return (
    <li>
      <div className="queue-row bulk-mock-row">
        <span className="priority-dot dot-mock" />
        <div className="row-main">
          <div className="row-top">
            <span className="sender">{email.sender}</span>
            <span className="received-at">
              {formatReceived(email.received_at)}
            </span>
          </div>
          <div className="subject">{email.subject}</div>
          <div className="row-tags">
            <span className="badge badge-mock">test data</span>
          </div>
        </div>
      </div>
    </li>
  );
}
