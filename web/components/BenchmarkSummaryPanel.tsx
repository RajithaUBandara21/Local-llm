"use client";

import { useBenchmark } from "@/lib/benchmark-context";

export function BenchmarkSummaryPanel() {
  const { metrics, metricsLoading, metricsError, metricsNotFound, modelSummaries } =
    useBenchmark();

  if (metricsError || metricsLoading || metricsNotFound || !metrics) {
    return null;
  }

  if (modelSummaries.length === 0) {
    return null;
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Last run summary</h2>
        <span className="hint">
          {metrics.latest_benchmark_file} &middot; {metrics.total_runs} total runs
        </span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Attempts</th>
            <th>Avg TTFT</th>
            <th>Avg latency</th>
            <th>Avg tokens/s</th>
            <th>Avg CPU</th>
            <th>Avg RAM</th>
            <th>Valid JSON</th>
          </tr>
        </thead>
        <tbody>
          {modelSummaries.map((summary) => (
            <tr key={summary.model}>
              <td className="cell-mono">{summary.model}</td>
              <td className="cell-muted">{summary.attempts}</td>
              <td className="cell-muted">{summary.avgTtftSec.toFixed(2)} s</td>
              <td className="cell-muted">{summary.avgLatencySec.toFixed(2)} s</td>
              <td className="cell-muted">{summary.avgTokensPerSec.toFixed(1)}</td>
              <td className="cell-muted">{summary.avgCpuPercent.toFixed(0)}%</td>
              <td className="cell-muted">{(summary.avgRamMb / 1024).toFixed(1)} GB</td>
              <td>
                <span className="status-pill completed">
                  {summary.validJsonPercent.toFixed(1)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
