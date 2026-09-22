"use client";

import { useReviewQueue } from "@/lib/review-queue-context";
import { QueueRow } from "./QueueRow";

export function QueuePanel() {
  const { filteredQueueItems, queueItems, filters, selectedId, select, loading, error } =
    useReviewQueue();

  const isFiltered = filters.priority !== "all" || filters.category !== "all";
  const hint = isFiltered
    ? `${filteredQueueItems.length} of ${queueItems.length} shown`
    : "urgent first";

  return (
    <div className="panel" id="listPanel">
      <div className="panel-header">
        <h2>Priority queue</h2>
        <span className="hint">{hint}</span>
      </div>
      {loading && <p className="empty-state">Loading...</p>}
      {error && <p className="empty-state">{error}</p>}
      {!loading && !error && (
        <ul className="queue-list">
          {filteredQueueItems.length === 0 && (
            <li className="empty-state">No emails match these filters.</li>
          )}
          {filteredQueueItems.map((email) => (
            <QueueRow
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
