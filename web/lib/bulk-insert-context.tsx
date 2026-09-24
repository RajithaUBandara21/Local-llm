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
import {
  ApiError,
  createBatch,
  deleteBatch,
  discardPendingMailboxFile,
  getBatches,
  getPendingMailboxFiles,
  resumeBatch,
  stopBatch,
  uploadMailboxFile,
  type PendingMailboxFile,
} from "./api";
import type { BatchStatus, MailSet } from "./types";

const POLL_MS = 3000;

interface BulkInsertContextValue {
  mailSets: MailSet[];
  addMailSet: (name: string, file: globalThis.File) => Promise<void>;
  processMailSet: (
    id: string,
    receivedAfter?: string,
    receivedBefore?: string
  ) => void;
  stopMailSet: (id: string) => void;
  removeMailSet: (id: string) => Promise<void>;
  // Mail set ids with a stop/delete request in flight, mapped to which action
  // is pending, so a row can disable its buttons and show a loading state
  // only on the button actually clicked instead of allowing repeat clicks to
  // fire more requests while the first is still pending.
  pendingActions: ReadonlyMap<string, "stop" | "delete">;
  selectedMailSetId: string | null;
  selectMailSet: (id: string | null) => void;
}

const BulkInsertContext = createContext<BulkInsertContextValue | null>(null);

// Both ids are derived from a stable server-issued value (the batch id, or
// the uploaded file's stored name), so a mail set keeps the same id across a
// refresh instead of a client-random one that would only last the session.
function mailSetIdForBatch(batchId: number): string {
  return `batch-${batchId}`;
}

function mailSetIdForPendingFile(file: string): string {
  return `pending-${file}`;
}

function statusFromBatch(batch: BatchStatus): MailSet["status"] {
  if (batch.status !== "completed") return batch.active ? "running" : "paused";
  const allFailed =
    batch.failed > 0 && batch.ok === 0 && batch.needs_review === 0;
  return allFailed ? "failed" : "completed";
}

function mailSetFromBatch(batch: BatchStatus): MailSet {
  return {
    id: mailSetIdForBatch(batch.id),
    name: batch.display_name,
    file: batch.source_file,
    status: statusFromBatch(batch),
    batch,
    error: null,
  };
}

function mailSetFromPendingFile(pending: PendingMailboxFile): MailSet {
  return {
    id: mailSetIdForPendingFile(pending.file),
    name: pending.display_name,
    file: pending.file,
    status: "pending",
    batch: null,
    error: null,
  };
}

function isBatchAlreadyRunningError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 400 && /already running/.test(err.message);
}

export function BulkInsertProvider({
  children,
}: Readonly<{ children: ReactNode }>) {
  // Both /api/batches and /api/mailbox-files are server-side sources of
  // truth (a started batch, and an uploaded file with no batch yet), so a
  // mail set survives a refresh at every stage instead of only after it
  // starts processing.
  const [pendingSets, setPendingSets] = useState<MailSet[]>([]);
  const [batchSets, setBatchSets] = useState<MailSet[]>([]);
  const [selectedMailSetId, setSelectedMailSetId] = useState<string | null>(
    null
  );
  const [pendingActions, setPendingActions] = useState<
    ReadonlyMap<string, "stop" | "delete">
  >(new Map());
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const markPending = useCallback((id: string, action: "stop" | "delete") => {
    setPendingActions((prev) => new Map(prev).set(id, action));
  }, []);

  const clearPending = useCallback((id: string) => {
    setPendingActions((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  }, []);

  const refreshBatches = useCallback(async () => {
    const batches = await getBatches();
    setBatchSets(batches.map(mailSetFromBatch));
    return batches;
  }, []);

  const refreshPendingFiles = useCallback(async () => {
    const files = await getPendingMailboxFiles();
    setPendingSets(files.map(mailSetFromPendingFile));
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function tick() {
      try {
        const [batches] = await Promise.all([refreshBatches(), refreshPendingFiles()]);
        if (cancelled) return;
        const anyActive = batches.some((b) => b.status !== "completed");
        pollTimerRef.current = setTimeout(tick, anyActive ? POLL_MS : POLL_MS * 4);
      } catch {
        if (cancelled) return;
        pollTimerRef.current = setTimeout(tick, POLL_MS * 4);
      }
    }

    tick();
    return () => {
      cancelled = true;
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, [refreshBatches, refreshPendingFiles]);

  const mailSets = useMemo(() => [...pendingSets, ...batchSets], [pendingSets, batchSets]);

  const addMailSet = useCallback(async (name: string, file: globalThis.File) => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      throw new Error("Enter a name for this mail set.");
    }
    if (!file) {
      throw new Error("Choose a mail collected file.");
    }
    let uploaded;
    try {
      uploaded = await uploadMailboxFile(file, trimmedName);
    } catch (err) {
      throw new Error(
        err instanceof ApiError ? err.message : "Could not upload this file."
      );
    }
    // The upload is now recorded server-side under this name; add it
    // immediately instead of waiting for the next poll tick.
    setPendingSets((prev) => [
      ...prev.filter((set) => set.file !== uploaded.file),
      {
        id: mailSetIdForPendingFile(uploaded.file),
        name: trimmedName,
        file: uploaded.file,
        status: "pending",
        batch: null,
        error: null,
      },
    ]);
  }, []);

  const processMailSet = useCallback(
    (id: string, receivedAfter?: string, receivedBefore?: string) => {
      const target = mailSets.find((set) => set.id === id);
      if (!target) return;

      // Only one batch can run at a time server-side; starting or resuming
      // a second one while another is active is a normal, expected
      // conflict, not a failure of this mail set - so it is alerted and
      // left in whatever state it was already in, not marked failed.
      if (mailSets.some((set) => set.id !== id && set.status === "running")) {
        const runningName = mailSets.find((set) => set.status === "running")?.name;
        window.alert(
          runningName
            ? `"${runningName}" is currently processing. Try this mail set again once it finishes.`
            : "Another mail set is currently processing. Try this mail set again once it finishes."
        );
        return;
      }

      // A mail set with a batch already exists server-side (paused, with
      // pending emails left after an earlier filtered or stopped run).
      // Continue that batch instead of starting a new one, honoring the
      // date range chosen for this resume over whatever remains pending.
      if (target.batch) {
        const batchId = target.batch.id;
        setBatchSets((prev) =>
          prev.map((set) =>
            set.id === id ? { ...set, status: "running", error: null } : set
          )
        );
        resumeBatch(batchId, receivedAfter, receivedBefore)
          .then(() => refreshBatches())
          .catch((err) => {
            const message =
              err instanceof ApiError ? err.message : "Could not resume this mail set.";
            if (isBatchAlreadyRunningError(err)) {
              window.alert(`${message} Try this mail set again once it finishes.`);
              setBatchSets((prev) =>
                prev.map((set) => (set.id === id ? { ...set, status: "paused" } : set))
              );
              return;
            }
            setBatchSets((prev) =>
              prev.map((set) =>
                set.id === id ? { ...set, status: "paused", error: message } : set
              )
            );
          });
        return;
      }

      setPendingSets((prev) =>
        prev.map((set) =>
          set.id === id ? { ...set, status: "running", error: null } : set
        )
      );
      createBatch(target.file, receivedAfter, receivedBefore)
        .then((batch) => {
          // The batch now exists server-side, which also clears this file's
          // pending-upload record there, so drop the client-only placeholder
          // and reconcile both lists against the server.
          setPendingSets((prev) => prev.filter((set) => set.id !== id));
          setBatchSets((prev) => [
            ...prev.filter((set) => set.id !== mailSetIdForBatch(batch.id)),
            mailSetFromBatch(batch),
          ]);
          Promise.all([refreshBatches(), refreshPendingFiles()]).catch(() => {
            // The regular poll loop reflects the real state either way.
          });
        })
        .catch((err) => {
          const message =
            err instanceof ApiError ? err.message : "Could not start this mail set.";
          if (isBatchAlreadyRunningError(err)) {
            window.alert(`${message} Try this mail set again once it finishes.`);
            setPendingSets((prev) =>
              prev.map((set) => (set.id === id ? { ...set, status: "pending" } : set))
            );
            return;
          }
          setPendingSets((prev) =>
            prev.map((set) =>
              set.id === id ? { ...set, status: "failed", error: message } : set
            )
          );
        });
    },
    [mailSets, refreshBatches, refreshPendingFiles]
  );

  const stopMailSet = useCallback(
    (id: string) => {
      if (pendingActions.has(id)) return;
      const target = mailSets.find((set) => set.id === id);
      if (!target?.batch) return;
      markPending(id, "stop");
      // The stop request only asks the backend to pause after the email
      // already in flight; the batch stays active until that finishes. Keep
      // the button disabled until a refreshed batch confirms it, instead of
      // clearing pending as soon as the request itself resolves.
      stopBatch(target.batch.id)
        .then(() => refreshBatches())
        .catch(() => {
          clearPending(id);
        });
    },
    [mailSets, pendingActions, markPending, clearPending, refreshBatches]
  );

  useEffect(() => {
    if (pendingActions.size === 0) return;
    for (const [id, action] of pendingActions) {
      if (action !== "stop") continue;
      const target = batchSets.find((set) => set.id === id);
      if (target?.batch && !target.batch.active) {
        clearPending(id);
      }
    }
  }, [batchSets, pendingActions, clearPending]);

  const removeMailSet = useCallback(
    async (id: string) => {
      if (pendingActions.has(id)) return;
      const target = mailSets.find((set) => set.id === id);
      if (!target) return;
      markPending(id, "delete");
      try {
        if (!target.batch) {
          await discardPendingMailboxFile(target.file);
          setPendingSets((prev) => prev.filter((set) => set.id !== id));
          return;
        }
        await deleteBatch(target.batch.id);
        setBatchSets((prev) => prev.filter((set) => set.id !== id));
        setSelectedMailSetId((current) => (current === id ? null : current));
      } finally {
        clearPending(id);
      }
    },
    [mailSets, pendingActions, markPending, clearPending]
  );

  const selectMailSet = useCallback((id: string | null) => {
    setSelectedMailSetId((current) => (current === id ? null : id));
  }, []);

  const value = useMemo(
    () => ({
      mailSets,
      addMailSet,
      processMailSet,
      stopMailSet,
      removeMailSet,
      pendingActions,
      selectedMailSetId,
      selectMailSet,
    }),
    [
      mailSets,
      addMailSet,
      processMailSet,
      stopMailSet,
      removeMailSet,
      pendingActions,
      selectedMailSetId,
      selectMailSet,
    ]
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
