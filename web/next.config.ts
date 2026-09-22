import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  // Pins the workspace root to this app so Turbopack ignores an unrelated
  // lockfile elsewhere on the machine (outside this git repo).
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
