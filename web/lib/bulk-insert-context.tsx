"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useMailbox } from "./mailbox-context";
import { MOCK_BATCH_SIZE, MOCK_INSERT_DELAY_MS } from "./constants";
import type { MockTestEmail } from "./types";

export type QueueMode = "live" | "bulk";

interface BulkInsertContextValue {
  mode: QueueMode;
  setMode: (mode: QueueMode) => void;
  mailbox: string | null;
  mockBatch: MockTestEmail[];
  processing: boolean;
  insertBatch: () => void;
  clearBatch: () => void;
}

const BulkInsertContext = createContext<BulkInsertContextValue | null>(null);

function buildMockBatch(mailbox: string): MockTestEmail[] {
  const now = Date.now();
  return Array.from({ length: MOCK_BATCH_SIZE }, (_, index) => {
    const n = index + 1;
    return {
      id: `mock-${n}`,
      mailbox,
      sender: `test.customer${n}@example.com`,
      subject: `Test email ${n}`,
      received_at: new Date(now - index * 60_000).toISOString(),
    };
  });
}

export function BulkInsertProvider({
  children,
}: Readonly<{ children: ReactNode }>) {
  const { currentMailbox } = useMailbox();
  const [mode, setMode] = useState<QueueMode>("live");
  const [mockBatch, setMockBatch] = useState<MockTestEmail[]>([]);
  const [processing, setProcessing] = useState(false);
  const insertTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset is derived state (mailbox changed), not an effect: adjust it during
  // render so a stale mock batch never appears under a different mailbox.
  const [trackedMailbox, setTrackedMailbox] = useState(currentMailbox);
  if (currentMailbox !== trackedMailbox) {
    setTrackedMailbox(currentMailbox);
    setMockBatch([]);
    setProcessing(false);
  }

  // The pending insert timer is an external resource, not state mirroring a
  // prop, so its cancellation belongs in an effect rather than the render-time
  // reset above.
  useEffect(() => {
    return () => {
      if (insertTimeoutRef.current) {
        clearTimeout(insertTimeoutRef.current);
        insertTimeoutRef.current = null;
      }
    };
  }, [currentMailbox]);

  const insertBatch = useCallback(() => {
    if (!currentMailbox || mockBatch.length > 0 || processing) return;
    const mailbox = currentMailbox;
    setProcessing(true);
    insertTimeoutRef.current = setTimeout(() => {
      setMockBatch(buildMockBatch(mailbox));
      setProcessing(false);
      insertTimeoutRef.current = null;
    }, MOCK_INSERT_DELAY_MS);
  }, [currentMailbox, mockBatch.length, processing]);

  const clearBatch = useCallback(() => {
    setMockBatch([]);
  }, []);

  const value = useMemo(
    () => ({
      mode,
      setMode,
      mailbox: currentMailbox,
      mockBatch,
      processing,
      insertBatch,
      clearBatch,
    }),
    [mode, currentMailbox, mockBatch, processing, insertBatch, clearBatch]
  );

  return (
    <BulkInsertContext.Provider value={value}>
      {children}
    </BulkInsertContext.Provider>
  );
}

export function useBulkInsert(): BulkInsertContextValue {
  const ctx = useContext(BulkInsertContext);
  if (!ctx) {
    throw new Error("useBulkInsert must be used within a BulkInsertProvider");
  }
  return ctx;
}
