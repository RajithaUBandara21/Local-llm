import type { Metadata } from "next";
import { AgentProvider } from "@/lib/agent-context";
import { MailboxProvider } from "@/lib/mailbox-context";
import { ReviewQueueProvider } from "@/lib/review-queue-context";
import { BulkInsertProvider } from "@/lib/bulk-insert-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Review - NorthPort Logistics",
  description: "Priority triage queue and manual review for support agents.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        <AgentProvider>
          <MailboxProvider>
            <BulkInsertProvider>
              <ReviewQueueProvider>{children}</ReviewQueueProvider>
            </BulkInsertProvider>
          </MailboxProvider>
        </AgentProvider>
      </body>
    </html>
  );
}
