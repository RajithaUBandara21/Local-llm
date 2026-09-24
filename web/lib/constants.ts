import type {
  Category,
  MockAccuracySummary,
  MockModelComparisonRow,
  Priority,
} from "./types";

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

// Benchmark screen (feature 24) placeholder triage-evaluation accuracy.
// Feature 27 owns the real numbers.
export const MOCK_ACCURACY_SUMMARY: MockAccuracySummary[] = [
  { model: "llama3.2", accuracyPercent: 87, sampleSize: 100 },
  { model: "phi-4-Q4", accuracyPercent: 91, sampleSize: 100 },
  { model: "mistral-7b-q4", accuracyPercent: 84, sampleSize: 100 },
  { model: "mistral-7b-Q5", accuracyPercent: 89, sampleSize: 100 },
];

// Benchmark screen (feature 24) placeholder Q4-vs-Q5 model comparison.
// Feature 28 owns the real numbers.
export const MOCK_MODEL_COMPARISON: MockModelComparisonRow[] = [
  { metric: "Avg. latency (sec)", q4Value: "2.1", q5Value: "2.6" },
  { metric: "Tokens / sec", q4Value: "34.5", q5Value: "28.2" },
  { metric: "Valid JSON rate", q4Value: "96%", q5Value: "98%" },
  { metric: "RAM usage (MB)", q4Value: "5,120", q5Value: "6,340" },
];
