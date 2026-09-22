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
        <span className="hint">{mailboxes.length} mailboxes</span>
      </div>

      {mailboxes.length === 0 ? (
        <p className="empty-state">No mailboxes yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Mailbox</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {mailboxes.map((mailbox) => (
              <tr key={mailbox}>
                <td className="cell-mono">{mailbox}</td>
                <td className="table-actions">
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    onClick={() => handleRemove(mailbox)}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="add-form">
        <div className="form-row">
          <div className="field">
            <label htmlFor="new-mailbox-name">New mailbox name</label>
            <input
              id="new-mailbox-name"
              type="text"
              placeholder="e.g. billing"
              value={newMailbox}
              onChange={(e) => setNewMailbox(e.target.value)}
            />
          </div>
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
      </div>

      <MailboxAssignmentsPanel
        mailboxes={mailboxes}
        selected={selected}
        onSelect={setSelected}
      />
    </section>
  );
}
