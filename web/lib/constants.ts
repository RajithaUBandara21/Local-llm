import type { Category, Priority } from "./types";

export const PRIORITIES: Priority[] = ["urgent", "high", "normal", "low"];

export const PRIORITY_ORDER: Record<Priority, number> = {
  urgent: 0,
  high: 1,
  normal: 2,
  low: 3,
};

export const CATEGORIES: Category[] = [
  "refund",
  "delivery",
  "billing",
  "complaint",
  "inquiry",
  "spam",
  "other",
];

// Fixed size of the mock batch the bulk-insert view (feature 22) generates.
// Feature 25 owns the real bulk-insert count/shape.
export const MOCK_BATCH_SIZE = 10;

// Simulated processing time after confirming a mock insert; stands in for
// the delay a real insert would have, with no backend meaning.
export const MOCK_INSERT_DELAY_MS = 700;
