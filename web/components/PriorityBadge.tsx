import type { Priority } from "@/lib/types";

export function PriorityBadge({ priority }: Readonly<{ priority: Priority }>) {
  return <span className={`badge badge-${priority}`}>{priority}</span>;
}
