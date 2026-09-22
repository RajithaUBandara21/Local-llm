"use client";

import { useState } from "react";
import type { MailboxEmail } from "@/lib/types";
import { PriorityBadge } from "./PriorityBadge";
import { ActionBar } from "./ActionBar";

export function EmailDetail({ email }: Readonly<{ email: MailboxEmail }>) {
  const result = email.triage?.result;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(result?.suggested_reply ?? "");

  // A newly selected email starts back in read mode with its own draft; this
  // is derived state (which email is showing), adjusted during render rather
  // than in an effect.
  const [trackedEmailId, setTrackedEmailId] = useState(email.id);
  if (email.id !== trackedEmailId) {
    setTrackedEmailId(email.id);
    setEditing(false);
    setDraft(result?.suggested_reply ?? "");
  }

  if (!result) return null;
  const hasReply = Boolean(result.suggested_reply);

  return (
    <div className="detail-body">
      <div className="detail-top">
        <div>
          <p className="detail-subject">{email.subject}</p>
          <p className="detail-sender">
            {email.sender} &middot; {email.mailbox}
          </p>
        </div>
        <div className="detail-meta">
          <PriorityBadge priority={result.priority} />
          <span className="tag-category">{result.category}</span>
        </div>
      </div>

      <div className="detail-grid">
        <div>
          <div className="stat-label">Category</div>
          <div className="stat-value" style={{ textTransform: "capitalize" }}>
            {result.category}
          </div>
        </div>
        <div>
          <div className="stat-label">Priority</div>
          <div className="stat-value" style={{ textTransform: "capitalize" }}>
            {result.priority}
          </div>
        </div>
        <div>
          <div className="stat-label">Confidence</div>
          <div className="stat-value">
            {Math.round(result.confidence * 100)}%
          </div>
        </div>
      </div>

      {result.flags.map((flag) => (
        <div key={flag} className="flag-note">
          <strong style={{ textTransform: "capitalize" }}>
            {flag.replace("_", " ")}:
          </strong>
          &nbsp;{result.flag_reason}
        </div>
      ))}

      <div className="detail-section">
        <h3>Original email</h3>
        <div className="original-email">{email.body_clean}</div>
      </div>

      <div className="detail-section">
        <h3>Summary</h3>
        <p>{result.summary}</p>
      </div>

      <div className="detail-section">
        <h3>Suggested reply</h3>
        {editing ? (
          <textarea
            className="reply-edit"
            aria-label="Edit suggested reply"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
        ) : (
          <div className={`reply-box${hasReply ? "" : " no-draft"}`}>
            {hasReply
              ? result.suggested_reply
              : "No draft - flagged out of policy."}
          </div>
        )}
      </div>

      <ActionBar
        email={email}
        hasReply={hasReply}
        editing={editing}
        draft={draft}
        onStartEdit={() => setEditing(true)}
        onCancelEdit={() => {
          setDraft(result.suggested_reply ?? "");
          setEditing(false);
        }}
      />
    </div>
  );
}
