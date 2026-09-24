"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError, getEmails } from "./api";
import { PRIORITY_ORDER } from "./constants";
import type {
  Category,
  ReviewableEmail,
  Priority,
  ReviewAction,
  TriageResult,
} from "./types";

export type ReviewView = "queue" | "manual";

export interface Filters {
  priority: Priority | "all";
  category: Category | "all";
}

const DEFAULT_FILTERS: Filters = { priority: "all", category: "all" };

interface ReviewQueueContextValue {
  loading: boolean;
  error: string | null;
  view: ReviewView;
  setView: (view: ReviewView) => void;
  filters: Filters;
  setFilters: (filters: Filters) => void;
  selectedId: number | null;
  select: (id: number | null) => void;
  queueItems: ReviewableEmail[];
  filteredQueueItems: ReviewableEmail[];
  manualReviewItems: ReviewableEmail[];
  selectedEmail: ReviewableEmail | null;
  applyReview: (emailId: number, review: ReviewAction) => void;
}

const ReviewQueueContext = createContext<ReviewQueueContextValue | null>(
  null
);

// A validated draft only ever exists once triage succeeded; this both narrows
// the type and is the single place that invariant is spelled out.
function okResult(email: ReviewableEmail): TriageResult | null {
  return email.triage?.status === "ok" ? email.triage.result : null;
}

function isPendingOk(email: ReviewableEmail): boolean {
  return okResult(email) !== null && email.review === null;
}

function isPendingManualReview(email: ReviewableEmail): boolean {
  return (
    (email.triage?.status === "needs_review" ||
      email.triage?.status === "failed") &&
    email.review === null
  );
}

export function ReviewQueueProvider({
  children,
}: Readonly<{ children: ReactNode }>) {
  const [emails, setEmails] = useState<ReviewableEmail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ReviewView>("queue");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const loaded = await getEmails();
        if (!cancelled) setEmails(loaded);
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof ApiError ? err.message : "Could not load emails."
        );
        setEmails([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const queueItems = useMemo(() => {
    return emails.filter(isPendingOk).sort((a, b) => {
      const aPriority = okResult(a)?.priority ?? "low";
      const bPriority = okResult(b)?.priority ?? "low";
      return PRIORITY_ORDER[aPriority] - PRIORITY_ORDER[bPriority];
    });
  }, [emails]);

  const filteredQueueItems = useMemo(() => {
    return queueItems.filter((email) => {
      const result = okResult(email);
      if (!result) return false;
      if (filters.priority !== "all" && result.priority !== filters.priority) {
        return false;
      }
      if (filters.category !== "all" && result.category !== filters.category) {
        return false;
      }
      return true;
    });
  }, [queueItems, filters]);

  const manualReviewItems = useMemo(
    () => emails.filter(isPendingManualReview),
    [emails]
  );

  const selectedEmail = useMemo(
    () => emails.find((email) => email.id === selectedId) ?? null,
    [emails, selectedId]
  );

  function select(id: number | null) {
    setSelectedId(id);
  }

  function applyReview(emailId: number, review: ReviewAction) {
    setEmails((current) =>
      current.map((email) =>
        email.id === emailId ? { ...email, review } : email
      )
    );
    setSelectedId((current) => (current === emailId ? null : current));
  }

  const value = useMemo(
    () => ({
      loading,
      error,
      view,
      setView,
      filters,
      setFilters,
      selectedId,
      select,
      queueItems,
      filteredQueueItems,
      manualReviewItems,
      selectedEmail,
      applyReview,
    }),
    [
      loading,
      error,
      view,
      filters,
      selectedId,
      queueItems,
      filteredQueueItems,
      manualReviewItems,
      selectedEmail,
    ]
  );

  return (
    <ReviewQueueContext.Provider value={value}>
      {children}
    </ReviewQueueContext.Provider>
  );
}

export function useReviewQueue(): ReviewQueueContextValue {
  const ctx = useContext(ReviewQueueContext);
  if (!ctx) {
    throw new Error(
      "useReviewQueue must be used within a ReviewQueueProvider"
    );
  }
  return ctx;
}
