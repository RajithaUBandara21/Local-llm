"use client";

import { useState } from "react";
import { useAdmin } from "@/lib/admin-context";
import { useGmail } from "@/lib/gmail-context";

export function GmailPanel() {
  const { mailboxes } = useAdmin();
  const { status, connectedMailbox, connectedEmail, connectedAt, connecting, connect, disconnect } =
    useGmail();
  const [selectedMailbox, setSelectedMailbox] = useState<string | null>(
    mailboxes[0] ?? null
  );

  const mailboxToConnect = selectedMailbox && mailboxes.includes(selectedMailbox)
    ? selectedMailbox
    : mailboxes[0] ?? null;

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Gmail connection</h2>
      </div>
      <div className="admin-panel-body">
        {status === "connected" ? (
          <>
            <p>
              Connected as <strong>{connectedEmail}</strong> for mailbox{" "}
              <strong>{connectedMailbox}</strong>.
            </p>
            <p className="admin-row-id">
              Connected at {connectedAt ? new Date(connectedAt).toLocaleString() : ""}
            </p>
            <button type="button" className="btn btn-reject" onClick={disconnect}>
              Disconnect
            </button>
          </>
        ) : (
          <>
            {mailboxes.length === 0 ? (
              <p className="empty-state">Add a mailbox before connecting Gmail.</p>
            ) : (
              <div className="control-group">
                <span className="filter-label">Mailbox</span>
                <select
                  className="mailbox-select"
                  value={mailboxToConnect ?? ""}
                  onChange={(e) => setSelectedMailbox(e.target.value)}
                  disabled={connecting}
                >
                  {mailboxes.map((mailbox) => (
                    <option key={mailbox} value={mailbox}>
                      {mailbox}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={connecting || !mailboxToConnect}
                  onClick={() => mailboxToConnect && connect(mailboxToConnect)}
                >
                  {connecting ? "Connecting..." : "Connect"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
