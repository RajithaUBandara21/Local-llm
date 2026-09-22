"use client";

import { useMailbox } from "@/lib/mailbox-context";

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function MailboxPicker() {
  const { mailboxes, currentMailbox, setCurrentMailbox, loading, error } =
    useMailbox();

  if (error) {
    return <span className="picker-error">{error}</span>;
  }

  return (
    <div className="control-group">
      <label className="filter-label" htmlFor="mailboxSelect">
        Mailbox
      </label>
      <select
        id="mailboxSelect"
        className="mailbox-select"
        title="Choose which mailbox's emails to review"
        value={currentMailbox ?? ""}
        disabled={loading || mailboxes.length === 0}
        onChange={(event) => setCurrentMailbox(event.target.value)}
      >
        {mailboxes.length === 0 && (
          <option value="">{loading ? "Loading..." : "No mailboxes"}</option>
        )}
        {mailboxes.map((mailbox) => (
          <option key={mailbox} value={mailbox}>
            {capitalize(mailbox)}
          </option>
        ))}
      </select>
    </div>
  );
}
