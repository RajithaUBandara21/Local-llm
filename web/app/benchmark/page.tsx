"use client";

import Link from "next/link";
import { BenchmarkRunPanel } from "@/components/BenchmarkRunPanel";
import { BenchmarkSummaryPanel } from "@/components/BenchmarkSummaryPanel";
import { BenchmarkMetricsPanel } from "@/components/BenchmarkMetricsPanel";
import { AccuracySummaryPanel } from "@/components/AccuracySummaryPanel";
import { ModelComparisonPanel } from "@/components/ModelComparisonPanel";
import { MOCK_ACCURACY_SUMMARY, MOCK_MODEL_COMPARISON } from "@/lib/constants";

export default function BenchmarkPage() {
  return (
    <>
      <header className="topbar">
        <div className="brand">
          NorthPort <span className="sep">/</span> Benchmark
        </div>
        <nav className="nav-tabs">
          <Link className="nav-tab" href="/">
            Mail queue
          </Link>
          <Link className="nav-tab" href="/admin">
            Admin
          </Link>
          <span className="nav-tab active">Benchmark</span>
        </nav>
      </header>

      <div className="page">
        <div className="page-header">
          <div>
            <h1 className="page-title">Benchmark testing</h1>
            <p className="page-subtitle">
              Queue one or more model/temperature configs, run them together as
              one benchmark, and review the resulting metrics from the shared
              CSV.
            </p>
          </div>
        </div>

        <BenchmarkRunPanel />
        <BenchmarkSummaryPanel />
        <BenchmarkMetricsPanel />

        <div className="admin-layout">
          <AccuracySummaryPanel rows={MOCK_ACCURACY_SUMMARY} />
          <ModelComparisonPanel rows={MOCK_MODEL_COMPARISON} />
        </div>
      </div>
    </>
  );
}
