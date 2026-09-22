import type { Metadata } from "next";
import { BenchmarkProvider } from "@/lib/benchmark-context";

export const metadata: Metadata = {
  title: "Benchmark - NorthPort Logistics",
  description: "Run and review local model benchmarks.",
};

export default function BenchmarkLayout({ children }: LayoutProps<"/benchmark">) {
  return <BenchmarkProvider>{children}</BenchmarkProvider>;
}
