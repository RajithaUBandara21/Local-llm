"use client";

import { useState } from "react";
import { useReviewQueue } from "@/lib/review-queue-context";
import { ManualReviewRow } from "./ManualReviewRow";
import { Pagination, PAGE_SIZE } from "./Pagination";

export function ManualReviewPanel() {
  const {
    manualReviewItems,
    filteredManualReviewItems,
    filters,
    selectedId,
    select,
    loading,
    error,
    hasUnprocessedSelection,
  } = useReviewQueue();
  const [page, setPage] = useState(1);

  const isFiltered = Boolean(filters.search);
  const hint = isFiltered
    ? `${filteredManualReviewItems.length} of ${manualReviewItems.length} shown`
    : "failures & timeouts";

  function emptyMessage(): string {
    if (hasUnprocessedSelection) return "This mail set has not been processed yet.";
    if (isFiltered) return "No emails match this search.";
    return "Nothing needs manual review.";
  }

  // Clamped during render rather than synced back with an effect: if the
  // filtered list shrinks below the requested page, this falls back to the
  // last valid page without an extra render round-trip.
  const totalPages = Math.max(1, Math.ceil(filteredManualReviewItems.length / PAGE_SIZE));
  const effectivePage = Math.min(page, totalPages);
  const pageItems = filteredManualReviewItems.slice(
    (effectivePage - 1) * PAGE_SIZE,
    effectivePage * PAGE_SIZE
  );

  return (
    <div className="panel" id="listPanel">
      <div className="panel-header">
        <h2>Manual review</h2>
        <span className="hint">{hint}</span>
      </div>
      {loading && <p className="empty-state">Loading...</p>}
      {error && <p className="empty-state">{error}</p>}
      {!loading && !error && (
        <>
          <ul className="queue-list">
            {filteredManualReviewItems.length === 0 && (
              <li className="empty-state">{emptyMessage()}</li>
            )}
            {pageItems.map((email) => (
              <ManualReviewRow
                key={email.id}
                email={email}
                selected={email.id === selectedId}
                onSelect={() => select(email.id)}
              />
            ))}
          </ul>
          <Pagination
            page={effectivePage}
            totalItems={filteredManualReviewItems.length}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
