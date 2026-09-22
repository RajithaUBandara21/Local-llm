"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  MOCK_GMAIL_ACCOUNT_EMAIL,
  MOCK_GMAIL_CONNECT_DELAY_MS,
} from "./constants";
import type { GmailConnectionStatus } from "./types";

interface GmailContextValue {
  status: GmailConnectionStatus;
  connectedMailbox: string | null;
  connectedEmail: string | null;
  connectedAt: string | null;
  connecting: boolean;
  connect: (mailbox: string) => void;
  disconnect: () => void;
}

const GmailContext = createContext<GmailContextValue | null>(null);

export function GmailProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [status, setStatus] = useState<GmailConnectionStatus>("disconnected");
  const [connectedMailbox, setConnectedMailbox] = useState<string | null>(null);
  const [connectedEmail, setConnectedEmail] = useState<string | null>(null);
  const [connectedAt, setConnectedAt] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const connectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback((mailbox: string) => {
    if (connecting || status === "connected") return;
    setConnecting(true);
    connectTimeoutRef.current = setTimeout(() => {
      setStatus("connected");
      setConnectedMailbox(mailbox);
      setConnectedEmail(MOCK_GMAIL_ACCOUNT_EMAIL);
      setConnectedAt(new Date().toISOString());
      setConnecting(false);
      connectTimeoutRef.current = null;
    }, MOCK_GMAIL_CONNECT_DELAY_MS);
  }, [connecting, status]);

  const disconnect = useCallback(() => {
    if (connectTimeoutRef.current) {
      clearTimeout(connectTimeoutRef.current);
      connectTimeoutRef.current = null;
    }
    setConnecting(false);
    setStatus("disconnected");
    setConnectedMailbox(null);
    setConnectedEmail(null);
    setConnectedAt(null);
  }, []);

  const value = useMemo(
    () => ({
      status,
      connectedMailbox,
      connectedEmail,
      connectedAt,
      connecting,
      connect,
      disconnect,
    }),
    [status, connectedMailbox, connectedEmail, connectedAt, connecting, connect, disconnect]
  );

  return (
    <GmailContext.Provider value={value}>{children}</GmailContext.Provider>
  );
}

export function useGmail(): GmailContextValue {
  const ctx = useContext(GmailContext);
  if (!ctx) {
    throw new Error("useGmail must be used within a GmailProvider");
  }
  return ctx;
}
