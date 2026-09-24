"use client";

import { useState } from "react";
import { useReviewQueue } from "@/lib/review-queue-context";
import { ApiError, submitReview } from "@/lib/api";
import type { ReviewableEmail, ReviewActionType } from "@/lib/types";

interface ActionBarProps {
  email: ReviewableEmail;
  hasReply: boolean;
  editing: boolean;
  draft: string;
  onStartEdit: () => void;
  onCancelEdit: () => void;
}

export function ActionBar({
  email,
  hasReply,
  editing,
  draft,
  onStartEdit,
  onCancelEdit,
}: Readonly<ActionBarProps>) {
  const { applyReview } = useReviewQueue();
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function act(action: ReviewActionType, editedReply?: string) {
    setSubmitting(true);
    setActionError(null);
    try {
      const result = await submitReview(email.id, action, editedReply);
      applyReview(email.id, result);
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Could not save that decision."
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (editing) {
    return (
      <div className="action-bar">
        <button
          type="button"
          className="btn btn-primary"
          disabled={submitting}
          title="Save your edited reply and approve it"
          onClick={() => act("edit", draft)}
        >
          Save edit
        </button>
        <button
          type="button"
          className="btn"
          disabled={submitting}
          title="Discard your changes and go back to the suggested reply"
          onClick={onCancelEdit}
        >
          Cancel
        </button>
        {actionError && (
          <span className="action-status reject">{actionError}</span>
        )}
      </div>
    );
  }

  return (
    <div className="action-bar">
      <button
        type="button"
        className="btn btn-approve"
        disabled={submitting}
        title="Approve the suggested reply and send it as-is"
        onClick={() => act("approve")}
      >
        Approve
      </button>
      <button
        type="button"
        className="btn"
        disabled={submitting || !hasReply}
        title="Edit the suggested reply before approving it"
        onClick={onStartEdit}
      >
        Edit
      </button>
      <button
        type="button"
        className="btn btn-reject"
        disabled={submitting}
        title="Reject this suggested reply; nothing is sent to the customer"
        onClick={() => act("reject")}
      >
        Reject
      </button>
      {actionError && (
        <span className="action-status reject">{actionError}</span>
      )}
    </div>
  );
}
