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
