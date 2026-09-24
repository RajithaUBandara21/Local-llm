"use client";

import { useState } from "react";
import { useReviewQueue } from "@/lib/review-queue-context";
import { Pagination, PAGE_SIZE } from "./Pagination";
import { QueueRow } from "./QueueRow";

export function QueuePanel() {
  const {
    filteredQueueItems,
    queueItems,
    filters,
    selectedId,
    select,
    loading,
    error,
    hasUnprocessedSelection,
  } = useReviewQueue();
  const [page, setPage] = useState(1);

  const isFiltered =
    filters.priority !== "all" || filters.category !== "all" || Boolean(filters.search);
  const hint = isFiltered
    ? `${filteredQueueItems.length} of ${queueItems.length} shown`
    : "urgent first";

  // Clamped during render rather than synced back with an effect: if the
  // filtered list shrinks below the requested page, this falls back to the
  // last valid page without an extra render round-trip.
  const totalPages = Math.max(1, Math.ceil(filteredQueueItems.length / PAGE_SIZE));
  const effectivePage = Math.min(page, totalPages);
  const pageItems = filteredQueueItems.slice(
    (effectivePage - 1) * PAGE_SIZE,
    effectivePage * PAGE_SIZE
  );

  return (
    <div className="panel" id="listPanel">
      <div className="panel-header">
        <h2>Priority queue</h2>
        <span className="hint">{hint}</span>
      </div>
      {loading && <p className="empty-state">Loading...</p>}
      {error && <p className="empty-state">{error}</p>}
      {!loading && !error && (
        <>
          <ul className="queue-list">
            {filteredQueueItems.length === 0 && (
              <li className="empty-state">
                {hasUnprocessedSelection
                  ? "This mail set has not been processed yet."
                  : "No emails match these filters."}
              </li>
            )}
            {pageItems.map((email) => (
              <QueueRow
                key={email.id}
                email={email}
                selected={email.id === selectedId}
                onSelect={() => select(email.id)}
              />
            ))}
          </ul>
          <Pagination
            page={effectivePage}
            totalItems={filteredQueueItems.length}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
