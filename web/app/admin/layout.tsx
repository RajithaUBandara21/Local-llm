import type { Metadata } from "next";
import { AdminProvider } from "@/lib/admin-context";
import { GmailProvider } from "@/lib/gmail-context";

export const metadata: Metadata = {
  title: "Admin - NorthPort Logistics",
  description: "Manage agents, mailboxes, mailbox assignments, and the Gmail connection.",
};

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <AdminProvider>
      <GmailProvider>{children}</GmailProvider>
    </AdminProvider>
  );
}
