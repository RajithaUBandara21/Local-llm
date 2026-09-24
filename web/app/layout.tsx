import type { Metadata } from "next";
import { ReviewQueueProvider } from "@/lib/review-queue-context";
import { BulkInsertProvider } from "@/lib/bulk-insert-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mail Review - NorthPort Logistics",
  description: "Priority triage queue and manual review.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        <BulkInsertProvider>
          <ReviewQueueProvider>{children}</ReviewQueueProvider>
        </BulkInsertProvider>
      </body>
    </html>
  );
}
