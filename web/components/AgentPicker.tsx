"use client";

import { useAgent } from "@/lib/agent-context";

export function AgentPicker() {
  const { agents, currentAgentId, setCurrentAgentId, loading, error } =
    useAgent();

  if (error) {
    return <span className="picker-error">{error}</span>;
  }
  if (loading) {
    return <span className="picker-loading">Loading agents...</span>;
  }

  return (
    <div className="control-group">
      <span className="filter-label">Agent</span>
      <div className="agent-buttons">
        {agents.map((agent) => (
          <button
            key={agent.id}
            type="button"
            className={`agent-btn${agent.id === currentAgentId ? " active" : ""}`}
            onClick={() => setCurrentAgentId(agent.id)}
            title={`Review mailboxes as ${agent.name}`}
          >
            {agent.name}
          </button>
        ))}
      </div>
    </div>
  );
}
