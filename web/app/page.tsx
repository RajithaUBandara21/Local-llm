"use client";

import { AgentPicker } from "@/components/AgentPicker";
import { MailboxPicker } from "@/components/MailboxPicker";
import { ViewToggle } from "@/components/ViewToggle";
import { FilterBar } from "@/components/FilterBar";
import { QueuePanel } from "@/components/QueuePanel";
import { ManualReviewPanel } from "@/components/ManualReviewPanel";
import { DetailPanel } from "@/components/DetailPanel";
import { BatchStatusBar } from "@/components/BatchStatusBar";
import { useReviewQueue } from "@/lib/review-queue-context";

export default function ReviewPage() {
  const { view } = useReviewQueue();

  return (
    <>
      <header className="topbar">
        <div className="brand">
          NorthPort Logistics <span className="sep">/</span> Agent Review
        </div>
        <div className="controls">
          <AgentPicker />
          <MailboxPicker />
          <ViewToggle />
          <FilterBar />
        </div>
      </header>

      <BatchStatusBar />

      <div className="layout">
        {view === "queue" ? <QueuePanel /> : <ManualReviewPanel />}
        <DetailPanel />
      </div>
    </>
  );
}
