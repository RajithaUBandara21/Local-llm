"use client";

import { useState } from "react";
import { useBulkInsert } from "@/lib/bulk-insert-context";
import type { MailSet } from "@/lib/types";
import { BulkInsertRow } from "./BulkInsertRow";
import { MailSetModal } from "./MailSetModal";
import { Pagination, PAGE_SIZE } from "./Pagination";
import { ProcessFilterModal } from "./ProcessFilterModal";

export function BulkInsertPanel() {
  const {
    mailSets,
    processMailSet,
    stopMailSet,
    removeMailSet,
    pendingActions,
    selectedMailSetId,
    selectMailSet,
  } = useBulkInsert();
  const [modalOpen, setModalOpen] = useState(false);
  const [filterTarget, setFilterTarget] = useState<
    { id: string; file: string; resumeBatchId?: number } | null
  >(null);
  const [page, setPage] = useState(1);

  // Clamped during render rather than synced back with an effect: if the
  // list shrinks (an item is deleted) below the requested page, this falls
  // back to the last valid page without an extra render round-trip.
  const totalPages = Math.max(1, Math.ceil(mailSets.length / PAGE_SIZE));
  const effectivePage = Math.min(page, totalPages);
  const pageItems = mailSets.slice(
    (effectivePage - 1) * PAGE_SIZE,
    effectivePage * PAGE_SIZE
  );

  function handleDelete(id: string, name: string) {
    if (!window.confirm(`Delete mail set "${name}"? This also deletes its processed emails.`)) {
      return;
    }
    removeMailSet(id).catch(() => {
      // Nothing to reconcile locally; the list re-derives from the server on the next poll.
    });
  }

  function handleProcess(mailSet: MailSet) {
    // A mail set that already has a batch is resuming a paused or stopped
    // run; the same date-filter flow applies, scoped to its still-pending
    // emails instead of the whole file.
    setFilterTarget({
      id: mailSet.id,
      file: mailSet.file,
      resumeBatchId: mailSet.batch?.id,
    });
  }

  return (
    <div className="panel bulk-panel" id="bulkPanel">
      <div className="panel-header">
        <h2>Mail sets</h2>
        <span className="hint">{mailSets.length} in list</span>
      </div>

      <div className="mail-set-add">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setModalOpen(true)}
        >
          Add mail set
        </button>
      </div>

      {mailSets.length === 0 ? (
        <p className="empty-state">
          No mail sets added yet. Add one above, then process it to run it
          through the pipeline.
        </p>
      ) : (
        <>
          <ul className="queue-list mail-set-list">
            {pageItems.map((mailSet) => (
              <BulkInsertRow
                key={mailSet.id}
                mailSet={mailSet}
                selected={mailSet.id === selectedMailSetId}
                onSelect={() => selectMailSet(mailSet.id)}
                onProcess={() => handleProcess(mailSet)}
                onStop={() => stopMailSet(mailSet.id)}
                onDelete={() => handleDelete(mailSet.id, mailSet.name)}
                pendingAction={pendingActions.get(mailSet.id) ?? null}
              />
            ))}
          </ul>
          <Pagination page={effectivePage} totalItems={mailSets.length} onPageChange={setPage} />
        </>
      )}

      {modalOpen && <MailSetModal onClose={() => setModalOpen(false)} />}
      {filterTarget && (
        <ProcessFilterModal
          file={filterTarget.file}
          resumeBatchId={filterTarget.resumeBatchId}
          onClose={() => setFilterTarget(null)}
          onConfirm={(receivedAfter, receivedBefore) =>
            processMailSet(filterTarget.id, receivedAfter, receivedBefore)
          }
        />
      )}
    </div>
  );
}
