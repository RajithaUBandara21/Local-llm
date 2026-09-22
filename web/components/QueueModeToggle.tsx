"use client";

import { useBulkInsert } from "@/lib/bulk-insert-context";

export function QueueModeToggle() {
  const { mode, setMode } = useBulkInsert();

  return (
    <div className="control-group">
      <div className="view-buttons">
        <button
          type="button"
          className={`view-btn${mode === "live" ? " active" : ""}`}
          title="Show the live, API-fetched priority queue"
          onClick={() => setMode("live")}
        >
          Live queue
        </button>
        <button
          type="button"
          className={`view-btn${mode === "bulk" ? " active" : ""}`}
          title="Insert a mock batch of test emails to try the dashboard without live data"
          onClick={() => setMode("bulk")}
        >
          Bulk insert
        </button>
      </div>
    </div>
  );
}
