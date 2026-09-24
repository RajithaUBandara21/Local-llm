import { formatReceivedAtFull } from "@/lib/format";
import type { ReviewableEmail } from "@/lib/types";

export function ManualReviewDetail({
  email,
}: Readonly<{ email: ReviewableEmail }>) {
  const triage = email.triage;
  if (!triage) return null;
  const failed = triage.status === "failed";

  return (
    <div className="mr-detail">
      <div className="detail-top">
        <div>
          <p className="detail-subject">{email.subject}</p>
          <p className="detail-sender">{email.sender}</p>
          <p className="detail-received-at">{formatReceivedAtFull(email.received_at)}</p>
        </div>
        <span className={`status-pill ${triage.status}`}>
          {failed ? "failed" : "needs review"}
        </span>
      </div>

      <div className={`mr-note-box${failed ? " failed" : ""}`}>
        {triage.failure_reason} ({triage.attempts} attempt
        {triage.attempts > 1 ? "s" : ""})
      </div>

      <div className="detail-section">
        <h3>Original email</h3>
        <div className="original-email">{email.body_clean}</div>
      </div>

      <div className="detail-section">
        <h3>Next step</h3>
        <p>
          No model output to review here - read the original email above and
          triage it by hand, then log the outcome.
        </p>
      </div>
    </div>
  );
}
