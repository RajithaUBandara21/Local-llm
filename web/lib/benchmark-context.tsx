"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  ApiError,
  getBenchmarkConfig,
  getBenchmarkMetrics,
  getBenchmarkStatus,
  startBenchmark,
} from "./api";
import type {
  BenchmarkConfig,
  BenchmarkConfigRow,
  BenchmarkMetrics,
  BenchmarkModelSummary,
  BenchmarkRunState,
} from "./types";

const STATUS_POLL_INTERVAL_MS = 2000;

function average(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

// The backend has no aggregation endpoint; these per-model averages are
// derived here from the same rows BenchmarkMetricsPanel already renders.
function summarizeByModel(rows: Record<string, string>[]): BenchmarkModelSummary[] {
  const byModel = new Map<string, Record<string, string>[]>();
  for (const row of rows) {
    const model = row.model ?? "unknown";
    const group = byModel.get(model) ?? [];
    group.push(row);
    byModel.set(model, group);
  }

  return Array.from(byModel.entries()).map(([model, modelRows]) => {
    const validCount = modelRows.filter((row) => row.is_valid_json === "True").length;
    return {
      model,
      attempts: modelRows.length,
      avgTtftSec: average(modelRows.map((row) => Number(row.ttft_sec) || 0)),
      avgLatencySec: average(modelRows.map((row) => Number(row.latency_sec) || 0)),
      avgTokensPerSec: average(modelRows.map((row) => Number(row.tokens_per_sec) || 0)),
      avgCpuPercent: average(modelRows.map((row) => Number(row.cpu_percent) || 0)),
      avgRamMb: average(modelRows.map((row) => Number(row.ram_mb) || 0)),
      validJsonPercent: modelRows.length === 0 ? 0 : (validCount / modelRows.length) * 100,
    };
  });
}

function makeRowId(): string {
  return Math.random().toString(36).slice(2);
}

interface BenchmarkContextValue {
  config: BenchmarkConfig | null;
  configLoading: boolean;
  configError: string | null;
  retryConfig: () => void;
  configRows: BenchmarkConfigRow[];
  addConfigRow: () => void;
  removeConfigRow: (id: string) => void;
  updateConfigRow: (id: string, changes: Partial<Omit<BenchmarkConfigRow, "id">>) => void;
  runsPerPrompt: number;
  setRunsPerPrompt: (runs: number) => void;
  runState: BenchmarkRunState;
  runError: string | null;
  start: () => void;
  metrics: BenchmarkMetrics | null;
  metricsLoading: boolean;
  metricsError: string | null;
  metricsNotFound: boolean;
  modelSummaries: BenchmarkModelSummary[];
}

const BenchmarkContext = createContext<BenchmarkContextValue | null>(null);

export function BenchmarkProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [config, setConfig] = useState<BenchmarkConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const [configReloadToken, setConfigReloadToken] = useState(0);

  const [configRows, setConfigRows] = useState<BenchmarkConfigRow[]>([]);
  const [runsPerPrompt, setRunsPerPrompt] = useState(1);

  const [runState, setRunState] = useState<BenchmarkRunState>("idle");
  const [runError, setRunError] = useState<string | null>(null);

  const [metrics, setMetrics] = useState<BenchmarkMetrics | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [metricsNotFound, setMetricsNotFound] = useState(false);
  const [metricsReloadToken, setMetricsReloadToken] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setConfigLoading(true);
    setConfigError(null);
    getBenchmarkConfig()
      .then((loaded) => {
        if (cancelled) return;
        setConfig(loaded);
        setRunsPerPrompt(loaded.default_runs_per_prompt);
        setConfigRows((current) =>
          current.length > 0
            ? current
            : loaded.models[0] && loaded.temperatures[0] !== undefined
              ? [{ id: makeRowId(), model: loaded.models[0], temperature: loaded.temperatures[0] }]
              : []
        );
      })
      .catch((err) => {
        if (cancelled) return;
        setConfigError(
          err instanceof ApiError ? err.message : "Could not load benchmark config."
        );
      })
      .finally(() => {
        if (!cancelled) setConfigLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [configReloadToken]);

  const loadMetrics = useCallback(() => {
    let cancelled = false;
    setMetricsLoading(true);
    setMetricsError(null);
    setMetricsNotFound(false);
    getBenchmarkMetrics()
      .then((loaded) => {
        if (cancelled) return;
        setMetrics(loaded);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setMetricsNotFound(true);
        } else {
          setMetricsError(
            err instanceof ApiError ? err.message : "Could not load benchmark metrics."
          );
        }
      })
      .finally(() => {
        if (!cancelled) setMetricsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return loadMetrics();
  }, [loadMetrics, metricsReloadToken]);

  // Detect an already-running benchmark on load so this screen can resume
  // polling instead of assuming idle.
  useEffect(() => {
    let cancelled = false;
    getBenchmarkStatus()
      .then(({ benchmark_running }) => {
        if (!cancelled && benchmark_running) {
          setRunState("running");
        }
      })
      .catch(() => {
        // Best-effort; the picker still works even if this check fails.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (runState !== "running") {
      return;
    }
    const interval = setInterval(() => {
      getBenchmarkStatus()
        .then(({ benchmark_running }) => {
          if (!benchmark_running) {
            setRunState("idle");
            setMetricsReloadToken((t) => t + 1);
          }
        })
        .catch(() => {
          // Keep polling; a transient failure shouldn't stop the run indicator.
        });
    }, STATUS_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [runState]);

  const retryConfig = useCallback(() => {
    setConfigReloadToken((t) => t + 1);
  }, []);

  const addConfigRow = useCallback(() => {
    setConfigRows((current) => {
      if (!config || config.models.length === 0 || config.temperatures.length === 0) {
        return current;
      }
      return [
        ...current,
        { id: makeRowId(), model: config.models[0], temperature: config.temperatures[0] },
      ];
    });
  }, [config]);

  const removeConfigRow = useCallback((id: string) => {
    setConfigRows((current) => current.filter((row) => row.id !== id));
  }, []);

  const updateConfigRow = useCallback(
    (id: string, changes: Partial<Omit<BenchmarkConfigRow, "id">>) => {
      setConfigRows((current) =>
        current.map((row) => (row.id === id ? { ...row, ...changes } : row))
      );
    },
    []
  );

  const start = useCallback(() => {
    if (configRows.length === 0) return;
    setRunState("starting");
    setRunError(null);
    startBenchmark(
      configRows.map(({ model, temperature }) => ({ model, temperature })),
      runsPerPrompt
    )
      .then(() => {
        setRunState("running");
      })
      .catch((err) => {
        setRunState("error");
        setRunError(
          err instanceof ApiError ? err.message : "Could not start the benchmark."
        );
      });
  }, [configRows, runsPerPrompt]);

  const modelSummaries = useMemo(
    () => (metrics ? summarizeByModel(metrics.data) : []),
    [metrics]
  );

  const value = useMemo(
    () => ({
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
      metrics,
      metricsLoading,
      metricsError,
      metricsNotFound,
      modelSummaries,
    }),
    [
      config,
      configLoading,
      configError,
      retryConfig,
      configRows,
      addConfigRow,
      removeConfigRow,
      updateConfigRow,
      runsPerPrompt,
      runState,
      runError,
      start,
      metrics,
      metricsLoading,
      metricsError,
      metricsNotFound,
      modelSummaries,
    ]
  );

  return (
    <BenchmarkContext.Provider value={value}>{children}</BenchmarkContext.Provider>
  );
}

export function useBenchmark(): BenchmarkContextValue {
  const ctx = useContext(BenchmarkContext);
  if (!ctx) {
    throw new Error("useBenchmark must be used within a BenchmarkProvider");
  }
  return ctx;
}
