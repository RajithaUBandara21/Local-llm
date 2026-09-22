"use client";

import { useAdmin } from "@/lib/admin-context";

interface MailboxAssignmentsPanelProps {
  mailboxes: string[];
  selected: string | null;
  onSelect: (mailbox: string) => void;
}

export function MailboxAssignmentsPanel({
  mailboxes,
  selected,
  onSelect,
}: Readonly<MailboxAssignmentsPanelProps>) {
  const { agents, assignments, toggleAssignment } = useAdmin();

  if (mailboxes.length === 0) {
    return null;
  }

  const activeMailbox = selected && mailboxes.includes(selected) ? selected : mailboxes[0];
  const assignedIds = assignments[activeMailbox] ?? [];

  return (
    <div className="admin-assignments">
      <div className="control-group">
        <span className="filter-label">Assignments for</span>
        <select
          className="mailbox-select"
          value={activeMailbox}
          onChange={(e) => onSelect(e.target.value)}
        >
          {mailboxes.map((mailbox) => (
            <option key={mailbox} value={mailbox}>
              {mailbox}
            </option>
          ))}
        </select>
      </div>

      {agents.length === 0 ? (
        <p className="empty-state">No agents to assign.</p>
      ) : (
        <ul className="admin-checklist">
          {agents.map((agent) => (
            <li key={agent.id} className="admin-checklist-row">
              <label>
                <input
                  type="checkbox"
                  checked={assignedIds.includes(agent.id)}
                  onChange={() => toggleAssignment(activeMailbox, agent.id)}
                />
                {agent.name}
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
