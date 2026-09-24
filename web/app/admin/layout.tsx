import type { Metadata } from "next";
import { GmailProvider } from "@/lib/gmail-context";

export const metadata: Metadata = {
  title: "Admin - NorthPort Logistics",
  description: "Manage the Gmail connection.",
};

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return <GmailProvider>{children}</GmailProvider>;
}
