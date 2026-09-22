"use client";

import { AgentPicker } from "@/components/AgentPicker";
import { MailboxPicker } from "@/components/MailboxPicker";
import { QueueModeToggle } from "@/components/QueueModeToggle";
import { ViewToggle } from "@/components/ViewToggle";
import { FilterBar } from "@/components/FilterBar";
import { QueuePanel } from "@/components/QueuePanel";
import { ManualReviewPanel } from "@/components/ManualReviewPanel";
import { BulkInsertPanel } from "@/components/BulkInsertPanel";
import { DetailPanel } from "@/components/DetailPanel";
import { BatchStatusBar } from "@/components/BatchStatusBar";
import { useReviewQueue } from "@/lib/review-queue-context";
import { useBulkInsert } from "@/lib/bulk-insert-context";

export default function ReviewPage() {
  const { view } = useReviewQueue();
  const { mode } = useBulkInsert();
  const isLive = mode === "live";

  return (
    <>
      <header className="topbar">
        <div className="brand">
          NorthPort Logistics <span className="sep">/</span> Agent Review
        </div>
        <div className="controls">
          <AgentPicker />
          <MailboxPicker />
          <QueueModeToggle />
          {isLive && <ViewToggle />}
          {isLive && <FilterBar />}
        </div>
      </header>

      <BatchStatusBar />

      <div className={isLive ? "layout" : "layout layout-single"}>
        {isLive ? (
          <>
            {view === "queue" ? <QueuePanel /> : <ManualReviewPanel />}
            <DetailPanel />
          </>
        ) : (
          <BulkInsertPanel />
        )}
      </div>
    </>
  );
}
