"use client";

import { useBenchmark } from "@/lib/benchmark-context";

export function BenchmarkRunPanel() {
  const {
    config,
    configLoading,
    configError,
    retryConfig,
    configRows,
    addConfigRow,
    removeConfigRow,
    updateConfigRow,
    runsPerPrompt,
    setRunsPerPrompt,
    runState,
    runError,
    start,
  } = useBenchmark();

  const isBusy = runState === "starting" || runState === "running";
  const canStart =
    !isBusy && configRows.length > 0 && configRows.every((row) => row.model && row.temperature !== undefined);
  const modelCountLabel = configRows.length === 1 ? "model" : "models";

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Run configuration</h2>
        <span className="hint">Wired to POST /api/benchmark/start</span>
      </div>

      {configError && (
        <div className="panel-body">
          <p className="picker-error">{configError}</p>
          <button type="button" className="btn" onClick={retryConfig}>
            Retry
          </button>
        </div>
      )}

      {!configError && configLoading && (
        <div className="panel-body">
          <p className="picker-loading">Loading model config...</p>
        </div>
      )}

      {!configError && !configLoading && config && (
        <>
          <div className="config-list">
            {configRows.map((row) => (
              <div key={row.id} className="config-row">
                <div className="field">
                  <label htmlFor={`benchmark-model-${row.id}`}>Model</label>
                  <select
                    id={`benchmark-model-${row.id}`}
                    value={row.model}
                    onChange={(e) => updateConfigRow(row.id, { model: e.target.value })}
                    disabled={isBusy}
                  >
                    {config.models.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label htmlFor={`benchmark-temperature-${row.id}`}>Temperature</label>
                  <select
                    id={`benchmark-temperature-${row.id}`}
                    value={row.temperature}
                    onChange={(e) =>
                      updateConfigRow(row.id, { temperature: Number(e.target.value) })
                    }
                    disabled={isBusy}
                  >
                    {config.temperatures.map((temperature) => (
                      <option key={temperature} value={temperature}>
                        {temperature}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  type="button"
                  className="btn btn-sm btn-danger config-remove"
                  disabled={isBusy || configRows.length === 1}
                  onClick={() => removeConfigRow(row.id)}
                >
                  Remove
                </button>
              </div>
            ))}

            <div className="config-add">
              <button type="button" className="btn btn-sm" disabled={isBusy} onClick={addConfigRow}>
                + Add model
              </button>
            </div>
          </div>

          <div className="run-bar" style={{ paddingTop: 0 }}>
            <div className="field">
              <label htmlFor="benchmark-runs">Runs per prompt</label>
              <input
                id="benchmark-runs"
                type="number"
                min={1}
                max={config.max_runs_per_prompt}
                value={runsPerPrompt}
                disabled={isBusy}
                onChange={(e) => setRunsPerPrompt(Number(e.target.value))}
              />
            </div>

            <button type="button" className="btn btn-primary" disabled={!canStart} onClick={start}>
              {isBusy ? "Running..." : `Run benchmark · ${configRows.length} ${modelCountLabel}`}
            </button>
          </div>

          {runError && (
            <p className="picker-error" style={{ padding: "0 16px 16px" }}>
              {runError}
            </p>
          )}

          {runState === "running" && (
            <div style={{ padding: "0 16px 16px" }}>
              <div className="progress-track">
                <div className="progress-fill progress-fill-indeterminate" />
              </div>
              <div className="progress-label">
                <span>Benchmark running...</span>
                <span className="status-pill running">Running</span>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
