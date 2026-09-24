"use client";

import Link from "next/link";
import { GmailPanel } from "@/components/GmailPanel";
import { ModelSettingsPanel } from "@/components/ModelSettingsPanel";

export default function AdminPage() {
  return (
    <>
      <header className="topbar">
        <div className="brand">
          NorthPort <span className="sep">/</span> Admin
        </div>
        <nav className="nav-tabs">
          <Link className="nav-tab" href="/">
            Mail queue
          </Link>
          <span className="nav-tab active">Admin</span>
          <Link className="nav-tab" href="/benchmark">
            Benchmark
          </Link>
        </nav>
      </header>

      <div className="page">
        <div className="page-header">
          <div>
            <h1 className="page-title">Admin</h1>
            <p className="page-subtitle">Manage the Gmail connection and processing model.</p>
          </div>
        </div>

        <div className="admin-layout">
          <GmailPanel />
          <ModelSettingsPanel />
        </div>
      </div>
    </>
  );
}
