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
          NorthPort Logistics <span className="sep">/</span> Admin
        </div>
        <div className="controls">
          <Link href="/" className="btn">
            Back to review page
          </Link>
        </div>
      </header>

      <div className="admin-layout">
        <AgentsPanel />

        <MailboxesPanel />

        <GmailPanel />
      </div>
    </>
  );
}
