import type { MockModelComparisonRow } from "@/lib/types";

interface Props {
  readonly rows: MockModelComparisonRow[];
}

// Placeholder panel; feature 28 replaces `rows` with the real Q4-vs-Q5
// comparison. Props-driven so that swap needs no change to this component.
export function ModelComparisonPanel({ rows }: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Q4 vs Q5 comparison</h2>
        <span className="hint badge-mock">mock data</span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Metric</th>
            <th>Q4</th>
            <th>Q5</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.metric}>
              <td>{row.metric}</td>
              <td className="cell-muted">{row.q4Value}</td>
              <td className="cell-muted">{row.q5Value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
