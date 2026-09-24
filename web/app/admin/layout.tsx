import type { Metadata } from "next";
import { GmailProvider } from "@/lib/gmail-context";
import { ModelSettingsProvider } from "@/lib/model-settings-context";

export const metadata: Metadata = {
  title: "Admin - NorthPort Logistics",
  description: "Manage the Gmail connection and processing model.",
};

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <GmailProvider>
      <ModelSettingsProvider>{children}</ModelSettingsProvider>
    </GmailProvider>
  );
}
