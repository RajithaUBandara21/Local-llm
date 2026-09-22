"use client";

import { useEffect, useState } from "react";
import { ApiError, getBatches } from "@/lib/api";
import type { BatchStatus } from "@/lib/types";

const POLL_MS = 3000;

function label(batch: BatchStatus): { text: string; className: string } {
  if (batch.status === "completed") return { text: "completed", className: "completed" };
  if (batch.active) return { text: "running", className: "running" };
  return { text: "paused", className: "paused" };
}

export function BatchStatusBar() {
  const [latest, setLatest] = useState<BatchStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      try {
        const batches = await getBatches();
        if (cancelled) return;
        const mostRecent = batches[0] ?? null;
        setLatest(mostRecent);
        setError(null);
        if (mostRecent?.active) {
          timer = setTimeout(poll, POLL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError ? err.message : "Could not load batch status."
        );
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []);

  if (error) {
    return <div className="batch-bar picker-error">{error}</div>;
  }
  if (!latest) return null;

  const { text, className } = label(latest);

  return (
    <div className="batch-bar">
      <span className="batch-file">{latest.source_file}</span>
      <span className={`status-pill ${className}`}>{text}</span>
      <span className="batch-progress">
        {latest.processed} / {latest.total} processed
      </span>
      <span className="batch-counts">
        <span className="batch-count ok">{latest.ok} ok</span>
        <span className="batch-count needs_review">
          {latest.needs_review} needs review
        </span>
        <span className="batch-count failed">{latest.failed} failed</span>
      </span>
    </div>
  );
}
