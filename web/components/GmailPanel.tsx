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

  if (mailboxes.length === 0) {
    return (
      <section className="panel">
        <div className="panel-header">
          <h2>Gmail connection</h2>
          <span className="hint">Opt-in live mail transport</span>
        </div>
        <p className="empty-state">Add a mailbox before connecting Gmail.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Gmail connection</h2>
        <span className="hint">Opt-in live mail transport</span>
      </div>

      {status === "connected" ? (
        <div className="gmail-card">
          <div className="gmail-account">
            <div className="gmail-icon">G</div>
            <div>
              <div className="gmail-email">{connectedEmail}</div>
              <div className="gmail-meta">
                Connected {connectedAt ? new Date(connectedAt).toLocaleString() : ""}
                &middot; {connectedMailbox} mailbox
              </div>
            </div>
          </div>
          <div className="gmail-actions">
            <span className="status-pill connected">Connected</span>
            <button type="button" className="btn btn-danger" onClick={disconnect}>
              Disconnect
            </button>
          </div>
        </div>
      ) : (
        <div className="gmail-card gmail-disconnected">
          <div className="gmail-account">
            <div className="gmail-icon">G</div>
            <div>
              <div className="gmail-email">Not connected</div>
              <div className="gmail-meta">
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
              </div>
            </div>
          </div>
          <div className="gmail-actions">
            <span className="status-pill disconnected">Disconnected</span>
            <button
              type="button"
              className="btn btn-primary"
              disabled={connecting || !mailboxToConnect}
              onClick={() => mailboxToConnect && connect(mailboxToConnect)}
            >
              {connecting ? "Connecting..." : "Connect Gmail"}
            </button>
          </div>
        </div>
      )}
      <p className="section-note">
        Mock only: OAuth connect/status/disconnect wires to a real Google account
        in feature 26.
      </p>
    </section>
  );
}
