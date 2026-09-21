# Discovery brief: NorthPort Logistics email triage

NorthPort Logistics is a fictional customer. All figures below come from the
project plan or simple arithmetic on it, and the SLA targets are placeholders.

## Customer

NorthPort Logistics, a logistics company whose support team handles customer
email through three shared mailboxes: support, refunds, and deliveries.

## Users

- **4 support agents** triage incoming email and approve, edit, or reject a
  suggested reply. Each agent sees only the mailboxes assigned to them.
- **1 team lead** wants a cross-mailbox view of batch status, manual-review
  volume, and model performance. This is planned for a later phase.

## Current workflow

About 1,500 emails arrive each week (roughly 375 per agent if split evenly).
Agents triage them by hand, deciding what each email is about and how urgent it
is. The new system would not send replies, and it would not delete or archive
mail.

## Pain point

Urgent emails, such as refund demands and delivery failures, get buried in the
queue, and a wrongly labeled priority causes a missed SLA. The fictional targets
are:

| Priority | Target response |
| --- | --- |
| urgent | 1 hour |
| high | 4 hours |
| normal | 1 business day |
| low | 3 business days |

The baseline is not measured. Minutes of handling per email and the current SLA
breach rate are figures to measure with NorthPort during discovery.

## Systems

Shared mailboxes, worked by hand. No other tools or vendors are assumed. The
proposed system reads exported mailbox files (mbox or CSV), asks a small local
language model for a category, priority, summary, and draft reply as validated
JSON, and puts every result in front of an agent for review.

## Constraints

- Emails contain customer PII, so nothing may leave the machine.
- The target is a laptop or small on-prem server with no GPU.
- Single tenant, internal trusted users, no SSO or real authentication.
- The project uses synthetic emails only.
- A human approves every draft. Replies are never sent, and legal, medical, or
  financial questions are flagged for a person.

## Success metric

- At least 90% correct priority label, so at most about 150 of the 1,500 weekly
  emails may carry the wrong priority (1,500 x 10%).
- Under 5 seconds per email, so at most about 125 minutes of model time for a
  week of mail (1,500 x 5 s = 7,500 s).
- Zero external network calls at runtime.
