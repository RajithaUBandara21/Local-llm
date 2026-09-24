"use client";

import { useReviewQueue } from "@/lib/review-queue-context";

export function ViewToggle() {
  const { view, setView, queueItems, manualReviewItems } = useReviewQueue();

  return (
    <div className="control-group">
      <div className="view-buttons">
        <button
          type="button"
          className={`view-btn view-btn-queue${view === "queue" ? " active" : ""}`}
          title="Show the priority-sorted queue"
          onClick={() => setView("queue")}
        >
          Queue <span className="count">{queueItems.length}</span>
        </button>
        <button
          type="button"
          className={`view-btn view-btn-manual${view === "manual" ? " active" : ""}`}
          title="Show emails that failed validation or timed out and need a manual look"
          onClick={() => setView("manual")}
        >
          Manual Review <span className="count">{manualReviewItems.length}</span>
        </button>
      </div>
    </div>
  );
}
