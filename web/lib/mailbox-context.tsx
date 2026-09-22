"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError, getMailboxes } from "./api";
import { useAgent } from "./agent-context";

interface MailboxContextValue {
  mailboxes: string[];
  currentMailbox: string | null;
  setCurrentMailbox: (mailbox: string) => void;
  loading: boolean;
  error: string | null;
}

const MailboxContext = createContext<MailboxContextValue | null>(null);

export function MailboxProvider({
  children,
}: Readonly<{ children: ReactNode }>) {
  const { currentAgentId } = useAgent();
  const [mailboxes, setMailboxes] = useState<string[]>([]);
  const [currentMailbox, setCurrentMailbox] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset is derived state (agent changed), not an effect: adjust it during
  // render so it lands before the fetch effect below ever sees the new id.
  const [trackedAgentId, setTrackedAgentId] = useState(currentAgentId);
  if (currentAgentId !== trackedAgentId) {
    setTrackedAgentId(currentAgentId);
    setMailboxes([]);
    setCurrentMailbox(null);
    setError(null);
  }

  useEffect(() => {
    if (!currentAgentId) {
      return;
    }
    let cancelled = false;

    async function load(agentId: string) {
      setLoading(true);
      setError(null);
      try {
        const loaded = await getMailboxes(agentId);
        if (cancelled) return;
        setMailboxes(loaded);
        setCurrentMailbox(loaded[0] ?? null);
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError ? err.message : "Could not load mailboxes."
        );
        setMailboxes([]);
        setCurrentMailbox(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load(currentAgentId);
    return () => {
      cancelled = true;
    };
  }, [currentAgentId]);

  const value = useMemo(
    () => ({ mailboxes, currentMailbox, setCurrentMailbox, loading, error }),
    [mailboxes, currentMailbox, loading, error]
  );

  return (
    <MailboxContext.Provider value={value}>{children}</MailboxContext.Provider>
  );
}

export function useMailbox(): MailboxContextValue {
  const ctx = useContext(MailboxContext);
  if (!ctx) {
    throw new Error("useMailbox must be used within a MailboxProvider");
  }
  return ctx;
}
