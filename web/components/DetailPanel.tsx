"use client";

import { useReviewQueue } from "@/lib/review-queue-context";
import { EmailDetail } from "./EmailDetail";
import { ManualReviewDetail } from "./ManualReviewDetail";

export function DetailPanel() {
  const { selectedEmail } = useReviewQueue();

  if (!selectedEmail) {
    return (
      <div className="panel" id="detailPanel">
        <div className="detail-empty">
          <div className="icon">&#9993;</div>
          <div>Select an email from the queue to review it.</div>
        </div>
      </div>
    );
  }

  const isManualReview =
    selectedEmail.triage?.status === "needs_review" ||
    selectedEmail.triage?.status === "failed";

  return (
    <div className="panel" id="detailPanel">
      {isManualReview ? (
        <ManualReviewDetail email={selectedEmail} />
      ) : (
        <EmailDetail email={selectedEmail} />
      )}
    </div>
  );
}
