"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { previewMailboxFile, previewPendingEmails } from "@/lib/api";

// datetime-local expects "YYYY-MM-DDTHH:mm" in local time, with no timezone suffix.
function toDatetimeLocal(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

// A "To" of exactly midnight on its date is what an untouched or date-only
// pick looks like in a datetime-local field; the user means through the end
// of that day, not that single instant, so extend it to 23:59:59 before
// comparing or submitting. A "To" with any other time was deliberately set
// and is used exactly as typed.
function endOfDayIfMidnight(to: string): string {
  if (!to || !to.endsWith("T00:00")) return to;
  return `${to.slice(0, 10)}T23:59:59`;
}

function inRange(iso: string, from: string, to: string): boolean {
  const value = new Date(iso).getTime();
  if (Number.isNaN(value)) return false;
  if (from && value < new Date(from).getTime()) return false;
  const effectiveTo = endOfDayIfMidnight(to);
  if (effectiveTo && value > new Date(effectiveTo).getTime()) return false;
  return true;
}

export function ProcessFilterModal({
  file,
  resumeBatchId,
  onClose,
  onConfirm,
}: Readonly<{
  file: string;
  resumeBatchId?: number;
  onClose: () => void;
  onConfirm: (receivedAfter?: string, receivedBefore?: string) => void;
}>) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [timestamps, setTimestamps] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    const preview =
      resumeBatchId === undefined
        ? previewMailboxFile(file)
        : previewPendingEmails(resumeBatchId);
    preview
      .then((result) => {
        if (cancelled) return;
        const known = result.received_at.filter(
          (value): value is string => value !== null
        );
        setTimestamps(known);
        if (known.length > 0) {
          const times = known.map((value) => new Date(value).getTime());
          setFrom(toDatetimeLocal(new Date(Math.min(...times)).toISOString()));
          setTo(toDatetimeLocal(new Date(Math.max(...times)).toISOString()));
        }
      })
      .catch(() => {
        // No preview available; fields stay blank and the count stays hidden.
      });
    return () => {
      cancelled = true;
    };
  }, [file, resumeBatchId]);

  const inRangeCount = useMemo(
    () => timestamps.filter((value) => inRange(value, from, to)).length,
    [timestamps, from, to]
  );

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onConfirm(from || undefined, endOfDayIfMidnight(to) || undefined);
    onClose();
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="processFilterModalTitle"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="processFilterModalTitle">
            {resumeBatchId === undefined ? "Filter before processing" : "Filter before resuming"}
          </h2>
          <button
            type="button"
            className="modal-close"
            title="Close"
            onClick={onClose}
          >
            &times;
          </button>
        </div>
        <form className="modal-body" onSubmit={handleSubmit}>
          <p className="modal-hint">
            {resumeBatchId === undefined
              ? "Only emails received in this range will be processed. Leave both blank to process every email in this mail set."
              : "Only the still-pending emails received in this range will be processed. Leave both blank to process every remaining email."}
          </p>

          <div className="field">
            <label htmlFor="receivedFrom">From</label>
            <input
              id="receivedFrom"
              type="datetime-local"
              value={from}
              onChange={(event) => setFrom(event.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="receivedTo">To</label>
            <input
              id="receivedTo"
              type="datetime-local"
              value={to}
              onChange={(event) => setTo(event.target.value)}
            />
          </div>

          {timestamps.length > 0 && (
            <p className="modal-hint">
              {inRangeCount} of {timestamps.length} emails in range
            </p>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-reject" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary">
              Process
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
