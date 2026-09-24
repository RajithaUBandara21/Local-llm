const SHORT_FORMAT = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

// Compact "Mar 2, 9:41 AM" form for list rows, where space is tight.
export function formatReceivedAtShort(receivedAt: string | null): string {
  if (!receivedAt) return "Unknown date";
  const date = new Date(receivedAt);
  if (Number.isNaN(date.getTime())) return "Unknown date";
  return SHORT_FORMAT.format(date);
}

// Full locale date and time for the detail panel, where space allows it.
export function formatReceivedAtFull(receivedAt: string | null): string {
  if (!receivedAt) return "Received date unknown";
  const date = new Date(receivedAt);
  if (Number.isNaN(date.getTime())) return "Received date unknown";
  return date.toLocaleString();
}
