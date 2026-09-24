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
import { useBulkInsert } from "./bulk-insert-context";
import { PRIORITY_ORDER } from "./constants";
import type {
  Category,
  ReviewableEmail,
  Priority,
  ReviewAction,
  TriageResult,
} from "./types";

export type ReviewView = "queue" | "manual";

export type SortOption = "priority" | "newest" | "oldest";

export interface Filters {
  priority: Priority | "all";
  category: Category | "all";
  // Case-insensitive substring match against the sender address.
  search: string;
}

const DEFAULT_FILTERS: Filters = {
  priority: "all",
  category: "all",
  search: "",
};

function matchesSearch(email: ReviewableEmail, search: string): boolean {
  const query = search.trim().toLowerCase();
  if (!query) return true;
  return email.sender.toLowerCase().includes(query);
}

function receivedAtMs(email: ReviewableEmail): number {
  if (!email.received_at) return Number.NEGATIVE_INFINITY;
  const value = new Date(email.received_at).getTime();
  return Number.isNaN(value) ? Number.NEGATIVE_INFINITY : value;
}

// Sorts by date/time when asked; "priority" leaves the incoming order
// alone, since Queue already sorted by priority and Manual Review has no
// priority tiers to reorder by.
function applySort<T extends ReviewableEmail>(items: T[], sortBy: SortOption): T[] {
  if (sortBy === "priority") return items;
  const sorted = [...items].sort((a, b) => receivedAtMs(a) - receivedAtMs(b));
  return sortBy === "oldest" ? sorted : sorted.reverse();
}

interface ReviewQueueContextValue {
  loading: boolean;
  error: string | null;
  view: ReviewView;
  setView: (view: ReviewView) => void;
  filters: Filters;
  setFilters: (filters: Filters) => void;
  sortBy: SortOption;
  setSortBy: (sortBy: SortOption) => void;
  selectedId: number | null;
  select: (id: number | null) => void;
  queueItems: ReviewableEmail[];
  filteredQueueItems: ReviewableEmail[];
  manualReviewItems: ReviewableEmail[];
  filteredManualReviewItems: ReviewableEmail[];
  selectedEmail: ReviewableEmail | null;
  applyReview: (emailId: number, review: ReviewAction) => void;
  // The selected mail set exists but has not started processing yet, so it
  // has no batch and no emails; panels use this for a clearer empty state.
  hasUnprocessedSelection: boolean;
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
  const { mailSets, selectedMailSetId } = useBulkInsert();
  const [emails, setEmails] = useState<ReviewableEmail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ReviewView>("queue");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [sortBy, setSortBy] = useState<SortOption>("priority");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Three distinct states: no mail set selected (undefined, show every
  // batch's emails), a selected mail set with a batch (its id, scope to
  // it), or a selected mail set with no batch yet - not started processing
  // - which must show nothing rather than falling through to "every batch".
  const selectedSet = useMemo(
    () => mailSets.find((set) => set.id === selectedMailSetId) ?? null,
    [mailSets, selectedMailSetId]
  );
  const hasUnprocessedSelection = selectedSet !== null && selectedSet.batch === null;
  const selectedBatchId = selectedSet?.batch?.id;

  // BulkInsertProvider already polls /api/batches every few seconds as the
  // single source of truth for batch progress; summing each mail set's
  // processed count turns that into one signal this effect can depend on,
  // so the email list re-fetches as a side effect of processing advancing
  // anywhere (any batch, since no mail set may be selected), instead of a
  // second independent poller or a manual refresh.
  const processedSignal = useMemo(
    () => mailSets.reduce((total, set) => total + (set.batch?.processed ?? 0), 0),
    [mailSets]
  );

  useEffect(() => {
    let cancelled = false;

    async function load() {
      // A mail set that has not started processing has no batch and
      // therefore no emails yet; show an empty list instead of fetching
      // (which would return every batch's emails, since undefined means
      // "no filter" to the API, not "this empty one").
      if (hasUnprocessedSelection) {
        setEmails([]);
        setError(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const loaded = await getEmails(selectedBatchId);
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
  }, [selectedBatchId, hasUnprocessedSelection, processedSignal]);

  // Priority is always the primary grouping; sortBy only orders emails
  // within the same priority tier (date/time), or leaves that order as-is
  // when sortBy is "priority" itself.
  const queueItems = useMemo(() => {
    const byPriority = emails.filter(isPendingOk).sort((a, b) => {
      const aPriority = okResult(a)?.priority ?? "low";
      const bPriority = okResult(b)?.priority ?? "low";
      return PRIORITY_ORDER[aPriority] - PRIORITY_ORDER[bPriority];
    });
    if (sortBy === "priority") return byPriority;
    const tiers = new Map<Priority, ReviewableEmail[]>();
    for (const email of byPriority) {
      const priority = okResult(email)?.priority ?? "low";
      const tier = tiers.get(priority);
      if (tier) tier.push(email);
      else tiers.set(priority, [email]);
    }
    return [...tiers.values()].flatMap((tier) => applySort(tier, sortBy));
  }, [emails, sortBy]);

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
      if (!matchesSearch(email, filters.search)) return false;
      return true;
    });
  }, [queueItems, filters]);

  const manualReviewItems = useMemo(
    () => applySort(emails.filter(isPendingManualReview), sortBy),
    [emails, sortBy]
  );

  const filteredManualReviewItems = useMemo(
    () => manualReviewItems.filter((email) => matchesSearch(email, filters.search)),
    [manualReviewItems, filters]
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
      sortBy,
      setSortBy,
      selectedId,
      select,
      queueItems,
      filteredQueueItems,
      manualReviewItems,
      filteredManualReviewItems,
      selectedEmail,
      applyReview,
      hasUnprocessedSelection,
    }),
    [
      loading,
      error,
      view,
      filters,
      sortBy,
      selectedId,
      hasUnprocessedSelection,
      queueItems,
      filteredQueueItems,
      manualReviewItems,
      filteredManualReviewItems,
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
