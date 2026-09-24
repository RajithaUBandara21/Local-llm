"use client";

import { CATEGORIES, PRIORITIES } from "@/lib/constants";
import { useReviewQueue, type SortOption } from "@/lib/review-queue-context";

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

const DEFAULT_FILTERS = {
  priority: "all",
  category: "all",
  search: "",
} as const;

const SORT_OPTIONS: { value: SortOption; label: string }[] = [
  { value: "priority", label: "Priority" },
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
];

export function FilterBar() {
  const { view, filters, setFilters, sortBy, setSortBy } = useReviewQueue();
  const isQueue = view === "queue";
  const isCleared =
    filters.priority === "all" && filters.category === "all" && !filters.search;

  return (
    <div className="control-group">
      <label className="filter-label" htmlFor="prioritySelect">
        Filter
      </label>
      <select
        id="prioritySelect"
        className="filter-select"
        title="Filter the queue by priority level"
        aria-label="Filter by priority"
        disabled={!isQueue}
        value={filters.priority}
        onChange={(event) =>
          setFilters({
            ...filters,
            priority: event.target.value as typeof filters.priority,
          })
        }
      >
        <option value="all">All priorities</option>
        {PRIORITIES.map((priority) => (
          <option key={priority} value={priority}>
            {capitalize(priority)}
          </option>
        ))}
      </select>
      <select
        id="categorySelect"
        className="filter-select"
        title="Filter the queue by category"
        aria-label="Filter by category"
        disabled={!isQueue}
        value={filters.category}
        onChange={(event) =>
          setFilters({
            ...filters,
            category: event.target.value as typeof filters.category,
          })
        }
      >
        <option value="all">All categories</option>
        {CATEGORIES.map((category) => (
          <option key={category} value={category}>
            {capitalize(category)}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="filter-clear"
        title="Reset every filter back to its default"
        disabled={isCleared}
        onClick={() => setFilters({ ...DEFAULT_FILTERS })}
      >
        Clear
      </button>

      <label className="filter-label" htmlFor="sortBySelect">
        Sort by
      </label>
      <select
        id="sortBySelect"
        className="filter-select"
        title="Sort emails within each priority level by date and time"
        aria-label="Sort by"
        value={sortBy}
        onChange={(event) => setSortBy(event.target.value as SortOption)}
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <input
        id="senderSearchInput"
        type="search"
        className="filter-select filter-search"
        placeholder="Search by email address"
        title="Find emails by sender address"
        aria-label="Search by sender email address"
        value={filters.search}
        onChange={(event) => setFilters({ ...filters, search: event.target.value })}
      />
    </div>
  );
}
