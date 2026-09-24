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
import { MOCK_BATCH_SIZE, MOCK_INSERT_DELAY_MS } from "./constants";
import type { MockTestEmail } from "./types";

export type QueueMode = "live" | "bulk";

interface BulkInsertContextValue {
  mode: QueueMode;
  setMode: (mode: QueueMode) => void;
  mockBatch: MockTestEmail[];
  processing: boolean;
  insertBatch: () => void;
  clearBatch: () => void;
}

const BulkInsertContext = createContext<BulkInsertContextValue | null>(null);

function buildMockBatch(): MockTestEmail[] {
  const now = Date.now();
  return Array.from({ length: MOCK_BATCH_SIZE }, (_, index) => {
    const n = index + 1;
    return {
      id: `mock-${n}`,
      sender: `test.customer${n}@example.com`,
      subject: `Test email ${n}`,
      received_at: new Date(now - index * 60_000).toISOString(),
    };
  });
}

export function BulkInsertProvider({
  children,
}: Readonly<{ children: ReactNode }>) {
  const [mode, setMode] = useState<QueueMode>("live");
  const [mockBatch, setMockBatch] = useState<MockTestEmail[]>([]);
  const [processing, setProcessing] = useState(false);
  const insertTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (insertTimeoutRef.current) {
        clearTimeout(insertTimeoutRef.current);
        insertTimeoutRef.current = null;
      }
    };
  }, []);

  const insertBatch = useCallback(() => {
    if (mockBatch.length > 0 || processing) return;
    setProcessing(true);
    insertTimeoutRef.current = setTimeout(() => {
      setMockBatch(buildMockBatch());
      setProcessing(false);
      insertTimeoutRef.current = null;
    }, MOCK_INSERT_DELAY_MS);
  }, [mockBatch.length, processing]);

  const clearBatch = useCallback(() => {
    setMockBatch([]);
  }, []);

  const value = useMemo(
    () => ({
      mode,
      setMode,
      mockBatch,
      processing,
      insertBatch,
      clearBatch,
    }),
    [mode, mockBatch, processing, insertBatch, clearBatch]
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
