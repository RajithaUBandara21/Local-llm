"use client";

import { useBenchmark } from "@/lib/benchmark-context";

function downloadCsv(fileName: string, rows: Record<string, string>[]) {
  if (rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const csvBody = rows
    .map((row) => headers.map((header) => `"${row[header] ?? ""}"`).join(","))
    .join("\n");
  const csvContent = `${headers.join(",")}\n${csvBody}`;

  const blob = new Blob([csvContent], { type: "text/csv" });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export function BenchmarkMetricsPanel() {
  const { metrics, metricsLoading, metricsError, metricsNotFound } = useBenchmark();

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Attempt results</h2>
        {metrics && metrics.data.length > 0 && (
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => downloadCsv(metrics.latest_benchmark_file, metrics.data)}
          >
            Export CSV
          </button>
        )}
      </div>

      {metricsError && <p className="empty-state">{metricsError}</p>}

      {!metricsError && metricsLoading && (
        <p className="picker-loading panel-body">Loading metrics...</p>
      )}

      {!metricsError && !metricsLoading && metricsNotFound && (
        <p className="empty-state">
          No benchmark data yet. Start a benchmark to generate a report.
        </p>
      )}

      {!metricsError && !metricsLoading && !metricsNotFound && metrics && (
        <>
          {metrics.data.length === 0 ? (
            <p className="empty-state">No rows in the latest benchmark file.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Prompt</th>
                  <th>Temp</th>
                  <th>Run</th>
                  <th>Attempt</th>
                  <th>Valid JSON</th>
                  <th>TTFT</th>
                  <th>Latency</th>
                  <th>Tokens/s</th>
                  <th>CPU %</th>
                  <th>RAM</th>
                </tr>
              </thead>
              <tbody>
                {metrics.data.map((row, index) => (
                  <tr key={index}>
                    <td className="cell-mono">{row.model}</td>
                    <td className="cell-muted">{row.prompt_id}</td>
                    <td>{row.temperature}</td>
                    <td>{row.run}</td>
                    <td>{row.attempt}</td>
                    <td>
                      <span
                        className={`status-pill ${row.is_valid_json === "True" ? "completed" : "invalid"}`}
                      >
                        {row.is_valid_json === "True" ? "Valid" : "Invalid"}
                      </span>
                    </td>
                    <td className="cell-muted">{Number(row.ttft_sec).toFixed(2)} s</td>
                    <td className="cell-muted">{Number(row.latency_sec).toFixed(2)} s</td>
                    <td className="cell-muted">{Number(row.tokens_per_sec).toFixed(1)}</td>
                    <td className="cell-muted">{row.cpu_percent}%</td>
                    <td className="cell-muted">{row.ram_mb} MB</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
