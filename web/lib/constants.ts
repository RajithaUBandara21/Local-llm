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

// Fixed mock Gmail account shown once a connection is simulated; feature 26
// owns the real OAuth identity.
export const MOCK_GMAIL_ACCOUNT_EMAIL = "northport.support@gmail.com";

// Simulated OAuth round-trip delay for the Gmail connect action; no backend
// meaning.
export const MOCK_GMAIL_CONNECT_DELAY_MS = 900;
