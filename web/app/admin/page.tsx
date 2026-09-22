"use client";

import Link from "next/link";
import { AgentsPanel } from "@/components/AgentsPanel";
import { MailboxesPanel } from "@/components/MailboxesPanel";
import { GmailPanel } from "@/components/GmailPanel";

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
            <h1 className="page-title">Agents &amp; mailboxes</h1>
            <p className="page-subtitle">
              Manage support agents, mailboxes, and who can open what.
            </p>
          </div>
        </div>

        <div className="admin-layout">
          <AgentsPanel />

          <MailboxesPanel />

          <GmailPanel />
        </div>
      </div>
    </>
  );
}
