"use client";

import { useState, type FormEvent } from "react";
import { useBulkInsert } from "@/lib/bulk-insert-context";

const ACCEPTED_EXTENSIONS = [".csv", ".mbox"];

function hasAcceptedExtension(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function MailSetModal({
  onClose,
}: Readonly<{ onClose: () => void }>) {
  const { addMailSet } = useBulkInsert();
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;
    if (!file) {
      setError("Choose a mail collected file.");
      return;
    }
    if (!hasAcceptedExtension(file.name)) {
      setError("File must be a .csv or .mbox mailbox file.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await addMailSet(name, file);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add this mail set.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mailSetModalTitle"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="mailSetModalTitle">Add mail set</h2>
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
          <div className="field">
            <label htmlFor="mailSetName">Mail set name</label>
            <input
              id="mailSetName"
              type="text"
              placeholder="e.g. Week 12 support inbox"
              value={name}
              onChange={(event) => setName(event.target.value)}
              autoFocus
            />
          </div>

          <div className="field">
            <label htmlFor="mailSetFile">Mail collected file</label>
            <input
              id="mailSetFile"
              type="file"
              accept=".csv,.mbox"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </div>

          {error && <p className="modal-error">{error}</p>}

          <div className="modal-actions">
            <button
              type="button"
              className="btn btn-reject"
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? "Adding..." : "Add mail set"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
