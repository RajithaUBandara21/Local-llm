"use client";

import { useState } from "react";
import { useAdmin } from "@/lib/admin-context";

export function AgentsPanel() {
  const { agents, loading, error, retry, addAgent, renameAgent, removeAgent } =
    useAdmin();
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");

  const trimmedId = newId.trim();
  const duplicateId = agents.some((a) => a.id === trimmedId);
  const canAdd = trimmedId.length > 0 && newName.trim().length > 0 && !duplicateId;

  function handleAdd() {
    if (!canAdd) return;
    addAgent(trimmedId, newName.trim());
    setNewId("");
    setNewName("");
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Agents</h2>
      </div>

      {error && (
        <div className="admin-panel-body">
          <p className="picker-error">{error}</p>
          <button type="button" className="btn" onClick={retry}>
            Retry
          </button>
        </div>
      )}

      {!error && loading && (
        <div className="admin-panel-body">
          <p className="picker-loading">Loading agents...</p>
        </div>
      )}

      {!error && !loading && (
        <>
          {agents.length === 0 ? (
            <p className="empty-state">No agents yet.</p>
          ) : (
            <ul className="admin-list">
              {agents.map((agent) => (
                <li key={agent.id} className="admin-row">
                  <span className="admin-row-id">{agent.id}</span>
                  <input
                    className="admin-input"
                    type="text"
                    value={agent.name}
                    onChange={(e) => renameAgent(agent.id, e.target.value)}
                    aria-label={`Name for agent ${agent.id}`}
                  />
                  <button
                    type="button"
                    className="btn btn-reject"
                    onClick={() => removeAgent(agent.id)}
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
              placeholder="agent id"
              value={newId}
              onChange={(e) => setNewId(e.target.value)}
              aria-label="New agent id"
            />
            <input
              className="admin-input"
              type="text"
              placeholder="display name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              aria-label="New agent display name"
            />
            <button
              type="button"
              className="btn btn-primary"
              disabled={!canAdd}
              onClick={handleAdd}
            >
              Add agent
            </button>
          </div>
          {duplicateId && trimmedId.length > 0 && (
            <p className="admin-form-error">
              Agent id &quot;{trimmedId}&quot; already exists.
            </p>
          )}
        </>
      )}
    </section>
  );
}
