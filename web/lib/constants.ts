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

// Admin dashboard (feature 23) mock mailbox/assignment fixture, mirroring
// data/agents.json's `mailboxes` object. No endpoint lists all mailboxes or
// all mailbox assignments across agents, so this seeds the admin screen's
// starting state instead of a live call. Feature 26 owns the real shape.
export const MOCK_MAILBOX_ASSIGNMENTS: Record<string, string[]> = {
  support: ["asha", "ben", "chen", "dana"],
  refunds: ["asha", "ben"],
  deliveries: ["chen", "dana"],
};

// Fixed mock Gmail account shown once a connection is simulated; feature 26
// owns the real OAuth identity.
export const MOCK_GMAIL_ACCOUNT_EMAIL = "northport.support@gmail.com";

// Simulated OAuth round-trip delay for the Gmail connect action; no backend
// meaning.
export const MOCK_GMAIL_CONNECT_DELAY_MS = 900;
