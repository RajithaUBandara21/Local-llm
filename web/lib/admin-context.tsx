"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError, getAgents } from "./api";
import { MOCK_MAILBOX_ASSIGNMENTS } from "./constants";
import type { AdminAgent, AdminAssignments } from "./types";

interface AdminContextValue {
  agents: AdminAgent[];
  loading: boolean;
  error: string | null;
  retry: () => void;
  mailboxes: string[];
  assignments: AdminAssignments;
  addAgent: (id: string, name: string) => void;
  renameAgent: (id: string, name: string) => void;
  removeAgent: (id: string) => void;
  addMailbox: (mailbox: string) => void;
  removeMailbox: (mailbox: string) => void;
  toggleAssignment: (mailbox: string, agentId: string) => void;
}

const AdminContext = createContext<AdminContextValue | null>(null);

function initialMailboxes(): string[] {
  return Object.keys(MOCK_MAILBOX_ASSIGNMENTS);
}

function initialAssignments(): AdminAssignments {
  return Object.fromEntries(
    Object.entries(MOCK_MAILBOX_ASSIGNMENTS).map(([mailbox, agentIds]) => [
      mailbox,
      [...agentIds],
    ])
  );
}

export function AdminProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [agents, setAgents] = useState<AdminAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [mailboxes, setMailboxes] = useState<string[]>(initialMailboxes);
  const [assignments, setAssignments] = useState<AdminAssignments>(
    initialAssignments
  );

  useEffect(() => {
    let cancelled = false;
    getAgents()
      .then((loaded) => {
        if (cancelled) return;
        setAgents(loaded);
        setError(null);
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
  }, [reloadToken]);

  const retry = useCallback(() => {
    setLoading(true);
    setError(null);
    setReloadToken((t) => t + 1);
  }, []);

  const addAgent = useCallback((id: string, name: string) => {
    setAgents((prev) => [...prev, { id, name }]);
  }, []);

  const renameAgent = useCallback((id: string, name: string) => {
    setAgents((prev) => prev.map((a) => (a.id === id ? { ...a, name } : a)));
  }, []);

  const removeAgent = useCallback((id: string) => {
    setAgents((prev) => prev.filter((a) => a.id !== id));
    setAssignments((prev) =>
      Object.fromEntries(
        Object.entries(prev).map(([mailbox, agentIds]) => [
          mailbox,
          agentIds.filter((agentId) => agentId !== id),
        ])
      )
    );
  }, []);

  const addMailbox = useCallback((mailbox: string) => {
    setMailboxes((prev) => [...prev, mailbox]);
    setAssignments((prev) => ({ ...prev, [mailbox]: [] }));
  }, []);

  const removeMailbox = useCallback((mailbox: string) => {
    setMailboxes((prev) => prev.filter((m) => m !== mailbox));
    setAssignments((prev) => {
      const next = { ...prev };
      delete next[mailbox];
      return next;
    });
  }, []);

  const toggleAssignment = useCallback((mailbox: string, agentId: string) => {
    setAssignments((prev) => {
      const current = prev[mailbox] ?? [];
      const next = current.includes(agentId)
        ? current.filter((id) => id !== agentId)
        : [...current, agentId];
      return { ...prev, [mailbox]: next };
    });
  }, []);

  const value = useMemo(
    () => ({
      agents,
      loading,
      error,
      retry,
      mailboxes,
      assignments,
      addAgent,
      renameAgent,
      removeAgent,
      addMailbox,
      removeMailbox,
      toggleAssignment,
    }),
    [
      agents,
      loading,
      error,
      retry,
      mailboxes,
      assignments,
      addAgent,
      renameAgent,
      removeAgent,
      addMailbox,
      removeMailbox,
      toggleAssignment,
    ]
  );

  return (
    <AdminContext.Provider value={value}>{children}</AdminContext.Provider>
  );
}

export function useAdmin(): AdminContextValue {
  const ctx = useContext(AdminContext);
  if (!ctx) {
    throw new Error("useAdmin must be used within an AdminProvider");
  }
  return ctx;
}
