"use client";

import { useReviewQueue } from "@/lib/review-queue-context";
import { ManualReviewRow } from "./ManualReviewRow";

export function ManualReviewPanel() {
  const { manualReviewItems, selectedId, select, loading, error } =
    useReviewQueue();

  return (
    <div className="panel" id="listPanel">
      <div className="panel-header">
        <h2>Manual review</h2>
        <span className="hint">failures &amp; timeouts</span>
      </div>
      {loading && <p className="empty-state">Loading...</p>}
      {error && <p className="empty-state">{error}</p>}
      {!loading && !error && (
        <ul className="queue-list">
          {manualReviewItems.length === 0 && (
            <li className="empty-state">Nothing needs manual review.</li>
          )}
          {manualReviewItems.map((email) => (
            <ManualReviewRow
              key={email.id}
              email={email}
              selected={email.id === selectedId}
              onSelect={() => select(email.id)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
