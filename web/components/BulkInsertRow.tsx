import type { MailSet } from "@/lib/types";

function statusLabel(set: MailSet): { text: string; className: string } {
  if (set.status === "running") return { text: "running", className: "running" };
  if (set.status === "paused") return { text: "paused", className: "paused" };
  if (set.status === "completed") return { text: "completed", className: "completed" };
  if (set.status === "failed") return { text: "failed", className: "failed" };
  return { text: "pending", className: "paused" };
}

export function BulkInsertRow({
  mailSet,
  selected,
  onSelect,
  onProcess,
  onStop,
  onDelete,
  pendingAction,
}: Readonly<{
  mailSet: MailSet;
  selected: boolean;
  onSelect: () => void;
  onProcess: () => void;
  onStop: () => void;
  onDelete: () => void;
  pendingAction: "stop" | "delete" | null;
}>) {
  const { text, className } = statusLabel(mailSet);
  const isBusy = mailSet.status === "running";
  const actionPending = pendingAction !== null;
  const canStop = isBusy && mailSet.batch !== null && !actionPending;

  return (
    <li>
      <button
        type="button"
        className={`mail-set-row${selected ? " selected" : ""}`}
        onClick={onSelect}
        title="Show only this mail set's emails in the queue"
      >
        <div className="mail-set-row-main">
          <span className="mail-set-file">{mailSet.name}</span>
          <span className={`status-pill ${className}`}>{text}</span>
        </div>
        {mailSet.batch && (
          <span className="mail-set-progress">
            {mailSet.batch.processed} / {mailSet.batch.total} processed
          </span>
        )}
        {mailSet.error && <span className="mail-set-error">{mailSet.error}</span>}
        <div className="mail-set-actions">
          {isBusy && (
            <button
              type="button"
              className="btn btn-reject"
              disabled={!canStop}
              title={
                canStop
                  ? "Pause this mail set after its current email"
                  : "Starting up, try again in a moment"
              }
              onClick={(event) => {
                event.stopPropagation();
                onStop();
              }}
            >
              {pendingAction === "stop" ? "Stopping..." : "Stop"}
            </button>
          )}
          <button
            type="button"
            className="btn btn-primary"
            disabled={isBusy || actionPending}
            title="Process this mail set"
            onClick={(event) => {
              event.stopPropagation();
              onProcess();
            }}
          >
            {isBusy ? "Processing..." : "Process"}
          </button>
          <button
            type="button"
            className="btn btn-reject"
            disabled={isBusy || actionPending}
            title={
              isBusy
                ? "Stop this mail set before deleting it"
                : "Delete this mail set and its processed emails"
            }
            onClick={(event) => {
              event.stopPropagation();
              onDelete();
            }}
          >
            {pendingAction === "delete" ? "Deleting..." : "Delete"}
          </button>
        </div>
      </button>
    </li>
  );
}
