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
        <span className="hint">{agents.length} agents</span>
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
            <table className="data-table">
              <thead>
                <tr>
                  <th>Id</th>
                  <th>Name</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {agents.map((agent) => (
                  <tr key={agent.id}>
                    <td className="cell-mono">{agent.id}</td>
                    <td>
                      <input
                        className="admin-input"
                        type="text"
                        value={agent.name}
                        onChange={(e) => renameAgent(agent.id, e.target.value)}
                        aria-label={`Name for agent ${agent.id}`}
                      />
                    </td>
                    <td className="table-actions">
                      <button
                        type="button"
                        className="btn btn-sm btn-danger"
                        onClick={() => removeAgent(agent.id)}
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
                <label htmlFor="new-agent-id">Agent id</label>
                <input
                  id="new-agent-id"
                  type="text"
                  placeholder="e.g. priya"
                  value={newId}
                  onChange={(e) => setNewId(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="new-agent-name">Display name</label>
                <input
                  id="new-agent-name"
                  type="text"
                  placeholder="e.g. Priya"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </div>
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
          </div>
        </>
      )}
    </section>
  );
}
