import type { ReviewableEmail } from "@/lib/types";
import { PriorityBadge } from "./PriorityBadge";

export function QueueRow({
  email,
  selected,
  onSelect,
}: Readonly<{
  email: ReviewableEmail;
  selected: boolean;
  onSelect: () => void;
}>) {
  const result = email.triage?.result;
  if (!result) return null;

  return (
    <li>
      <button
        type="button"
        className={`queue-row${selected ? " selected" : ""}`}
        onClick={onSelect}
      >
        <span className={`priority-dot dot-${result.priority}`} />
        <div className="row-main">
          <div className="row-top">
            <span className="sender">{email.sender}</span>
            <span className="confidence">
              {Math.round(result.confidence * 100)}%
            </span>
          </div>
          <div className="subject">{email.subject}</div>
          <div className="row-tags">
            <PriorityBadge priority={result.priority} />
            <span className="tag-category">{result.category}</span>
            {result.flags.map((flag) => (
              <span key={flag} className="tag-flag">
                {flag.replace("_", " ")}
              </span>
            ))}
          </div>
        </div>
      </button>
    </li>
  );
}
