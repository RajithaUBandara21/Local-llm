import { formatReceivedAtShort } from "@/lib/format";
import type { ReviewableEmail } from "@/lib/types";

export function ManualReviewRow({
  email,
  selected,
  onSelect,
}: Readonly<{
  email: ReviewableEmail;
  selected: boolean;
  onSelect: () => void;
}>) {
  const status = email.triage?.status;
  if (status !== "needs_review" && status !== "failed") return null;

  return (
    <li>
      <button
        type="button"
        className={`mr-row${status === "failed" ? " status-failed" : ""}${
          selected ? " selected" : ""
        }`}
        onClick={onSelect}
      >
        <div className="row-main">
          <div className="row-top">
            <span className="sender">{email.sender}</span>
            <span className="confidence">
              {formatReceivedAtShort(email.received_at)}
            </span>
          </div>
          <div className="subject">{email.subject}</div>
          <div className="mr-note">{email.triage?.failure_reason}</div>
        </div>
        <span className={`status-pill ${status}`}>
          {status === "failed" ? "failed" : "needs review"}
        </span>
      </button>
    </li>
  );
}
