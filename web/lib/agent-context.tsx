"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError, getAgents } from "./api";
import type { Agent } from "./types";

const STORAGE_KEY = "northport-agent-id";

interface AgentContextValue {
  agents: Agent[];
  currentAgentId: string | null;
  setCurrentAgentId: (id: string) => void;
  loading: boolean;
  error: string | null;
}

const AgentContext = createContext<AgentContextValue | null>(null);

function readStoredAgentId(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredAgentId(id: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // Per-viewer convenience only; losing it just means no remembered agent.
  }
}

export function AgentProvider({
  children,
}: Readonly<{ children: ReactNode }>) {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [currentAgentId, setCurrentAgentIdState] = useState<string | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAgents()
      .then((loaded) => {
        if (cancelled) return;
        setAgents(loaded);
        const stored = readStoredAgentId();
        const initial =
          (stored && loaded.some((a) => a.id === stored) && stored) ||
          loaded[0]?.id ||
          null;
        setCurrentAgentIdState(initial);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Could not load agents.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function setCurrentAgentId(id: string) {
    setCurrentAgentIdState(id);
    writeStoredAgentId(id);
  }

  const value = useMemo(
    () => ({ agents, currentAgentId, setCurrentAgentId, loading, error }),
    [agents, currentAgentId, loading, error]
  );

  return (
    <AgentContext.Provider value={value}>{children}</AgentContext.Provider>
  );
}

export function useAgent(): AgentContextValue {
  const ctx = useContext(AgentContext);
  if (!ctx) {
    throw new Error("useAgent must be used within an AgentProvider");
  }
  return ctx;
}
