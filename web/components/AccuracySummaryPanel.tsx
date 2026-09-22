import type { MockAccuracySummary } from "@/lib/types";

interface Props {
  readonly rows: MockAccuracySummary[];
}

// Placeholder panel; feature 27 replaces `rows` with real triage-evaluation
// accuracy. Props-driven so that swap needs no change to this component.
export function AccuracySummaryPanel({ rows }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Triage-evaluation accuracy</h2>
        <span className="hint badge-mock">mock data</span>
      </div>
      <ul className="admin-list">
        {rows.map((row) => (
          <li key={row.model} className="admin-row">
            <span className="admin-row-id">{row.model}</span>
            <span>{row.accuracyPercent}% accurate</span>
            <span className="received-at">n={row.sampleSize}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
