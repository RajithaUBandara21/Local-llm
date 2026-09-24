"use client";

import { useGmail } from "@/lib/gmail-context";

export function GmailPanel() {
  const { status, connectedEmail, connectedAt, connecting, connect, disconnect } =
    useGmail();

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
            <div className="gmail-email">Not connected</div>
          </div>
          <div className="gmail-actions">
            <span className="status-pill disconnected">Disconnected</span>
            <button
              type="button"
              className="btn btn-primary"
              disabled={connecting}
              onClick={connect}
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
