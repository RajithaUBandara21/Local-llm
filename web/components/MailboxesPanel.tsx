"use client";

import { useState } from "react";
import { useAdmin } from "@/lib/admin-context";
import { MailboxAssignmentsPanel } from "@/components/MailboxAssignmentsPanel";

export function MailboxesPanel() {
  const { mailboxes, addMailbox, removeMailbox } = useAdmin();
  const [newMailbox, setNewMailbox] = useState("");
  const [selected, setSelected] = useState<string | null>(mailboxes[0] ?? null);

  const trimmed = newMailbox.trim();
  const duplicate = mailboxes.includes(trimmed);
  const canAdd = trimmed.length > 0 && !duplicate;

  function handleAdd() {
    if (!canAdd) return;
    addMailbox(trimmed);
    setSelected(trimmed);
    setNewMailbox("");
  }

  function handleRemove(mailbox: string) {
    removeMailbox(mailbox);
    if (selected === mailbox) {
      setSelected(null);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Mailboxes</h2>
      </div>

      {mailboxes.length === 0 ? (
        <p className="empty-state">No mailboxes yet.</p>
      ) : (
        <ul className="admin-list">
          {mailboxes.map((mailbox) => (
            <li key={mailbox} className="admin-row">
              <span className="admin-row-id">{mailbox}</span>
              <button
                type="button"
                className="btn btn-reject"
                onClick={() => handleRemove(mailbox)}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="admin-add-form">
        <input
          className="admin-input"
          type="text"
          placeholder="mailbox name"
          value={newMailbox}
          onChange={(e) => setNewMailbox(e.target.value)}
          aria-label="New mailbox name"
        />
        <button
          type="button"
          className="btn btn-primary"
          disabled={!canAdd}
          onClick={handleAdd}
        >
          Add mailbox
        </button>
      </div>
      {duplicate && trimmed.length > 0 && (
        <p className="admin-form-error">
          Mailbox &quot;{trimmed}&quot; already exists.
        </p>
      )}

      <MailboxAssignmentsPanel
        mailboxes={mailboxes}
        selected={selected}
        onSelect={setSelected}
      />
    </section>
  );
}
