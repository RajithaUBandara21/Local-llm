"use client";

import { CATEGORIES, PRIORITIES } from "@/lib/constants";
import { useReviewQueue } from "@/lib/review-queue-context";

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function FilterBar() {
  const { view, filters, setFilters } = useReviewQueue();
  const disabled = view !== "queue";
  const isCleared = filters.priority === "all" && filters.category === "all";

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
        disabled={disabled}
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
        disabled={disabled}
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
        title="Reset both filters back to all priorities and categories"
        disabled={disabled || isCleared}
        onClick={() => setFilters({ priority: "all", category: "all" })}
      >
        Clear
      </button>
    </div>
  );
}
