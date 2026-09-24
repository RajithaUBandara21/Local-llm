"use client";

import Link from "next/link";
import { ViewToggle } from "@/components/ViewToggle";
import { FilterBar } from "@/components/FilterBar";
import { QueuePanel } from "@/components/QueuePanel";
import { ManualReviewPanel } from "@/components/ManualReviewPanel";
import { BulkInsertPanel } from "@/components/BulkInsertPanel";
import { DetailPanel } from "@/components/DetailPanel";
import { useReviewQueue } from "@/lib/review-queue-context";

export default function ReviewPage() {
  const { view } = useReviewQueue();

  return (
    <>
      <header className="topbar">
        <div className="brand">
          NorthPort <span className="sep">/</span> Mail queue
        </div>
        <nav className="nav-tabs">
          <span className="nav-tab active">Mail queue</span>
          <Link className="nav-tab" href="/admin">
            Admin
          </Link>
          <Link className="nav-tab" href="/benchmark">
            Benchmark
          </Link>
        </nav>
        <div className="controls">
          <ViewToggle />
          <FilterBar />
        </div>
      </header>

      <div className="layout layout-with-mail-sets">
        <BulkInsertPanel />
        {view === "queue" ? <QueuePanel /> : <ManualReviewPanel />}
        <DetailPanel />
      </div>
    </>
  );
}
