"use client";

import { useBulkInsert } from "@/lib/bulk-insert-context";
import { BulkInsertRow } from "./BulkInsertRow";

export function BulkInsertPanel() {
  const { mailbox, mockBatch, processing, insertBatch, clearBatch } =
    useBulkInsert();
  const hasBatch = mockBatch.length > 0;

  let hint = "no test batch";
  if (processing) hint = "processing...";
  else if (hasBatch) hint = `${mockBatch.length} test emails`;

  return (
    <div className="panel bulk-panel" id="bulkPanel">
      <div className="panel-header">
        <h2>Bulk insert - {mailbox ?? "no mailbox"}</h2>
        <span className="hint">{hint}</span>
      </div>

      <p className="bulk-notice">
        Mock only: test emails are generated in the browser, are never sent to
        the server, and disappear on refresh. The real bulk-insert/clear
        backend is a later feature.
      </p>

      <div className="bulk-actions">
        {hasBatch ? (
          <button
            type="button"
            className="btn btn-reject"
            title="Remove the inserted mock test emails"
            onClick={clearBatch}
          >
            Clear test batch
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            disabled={!mailbox || processing}
            title="Insert a mock batch of test emails into the selected mailbox"
            onClick={insertBatch}
          >
            Insert test batch
          </button>
        )}
      </div>

      {processing && <p className="empty-state">Processing test batch...</p>}
      {!processing && hasBatch && (
        <ul className="queue-list bulk-list">
          {mockBatch.map((email) => (
            <BulkInsertRow key={email.id} email={email} />
          ))}
        </ul>
      )}
      {!processing && !hasBatch && (
        <p className="empty-state">
          No test batch inserted yet. Insert one to try the dashboard without
          live data.
        </p>
      )}
    </div>
  );
}
