# Email dataset

`northport_emails.csv` holds 100 synthetic support emails for the fictional
NorthPort Logistics, each labeled with a `category` and a `priority`. It is the
ground truth for triage evaluation.

## Provenance

Claude wrote the emails and assigned the labels ahead of time; the running system
never generates data. Everything is invented: names, addresses, order and
tracking numbers, and phone numbers (`555-0100` to `555-0199`). Sender addresses
use reserved domains (`example.com`, `example.org`, `example.net`, `.example`,
`.test`, `.invalid`). The labels follow the rules below but have not been checked
by a person yet.

## Columns

| Column | Meaning |
|---|---|
| `id` | `E001` to `E100`, equal to the row number |
| `mailbox` | `support`, `refunds`, or `deliveries` |
| `sender` | plain address on a reserved domain |
| `subject` | subject line as typed |
| `body` | raw body, plain text or HTML, with any signature and quoted history a real client would add |
| `received_at` | ISO 8601 with offset |
| `category` | `refund`, `delivery`, `billing`, `complaint`, `inquiry`, `spam`, or `other` |
| `priority` | `urgent`, `high`, `normal`, or `low` |

## Loading

`CsvEmailLoader` reads the file and ignores `id`, `mailbox`, `category`, and
`priority`. It returns one email per row in row order, so the Nth loaded email
has the labels on row N.

```python
from pathlib import Path
from app.loaders.factory import get_email_loader

path = Path("data/northport_emails.csv")
emails = get_email_loader(path).load(path)
```

Read the labels with the `csv` module (`csv.DictReader`, `encoding="utf-8"`,
`newline=""`).

## Category guide

The customer's main ask decides the category. For example, a refund demand about
a late parcel is `refund`, while a plain "where is my parcel" is `delivery`.

- `refund`: the customer wants money back for an order or shipment
- `delivery`: where a parcel is, late, lost, damaged, or misdelivered, and
  address or delivery-window changes
- `billing`: invoices, charges, payment methods, double or wrong charges, invoice
  copies (not a request for money back for the shipment itself)
- `complaint`: dissatisfaction with service, staff, or experience where the main
  ask is not a refund or a status
- `inquiry`: pre-sale or general questions, quotes, service coverage, policies
- `spam`: unsolicited marketing, phishing, and scams
- `other`: anything else legitimate: thanks and feedback, careers, wrong-recipient
  mail, partnership or research requests, subscribed newsletters

## Priority rules

Category is independent of priority. Priority comes from money or legal exposure,
time-sensitivity, and repeat contact. When unsure between two levels, the higher
one is used. Spam is always `low`. Every label can be worked out from the email
text alone. The response targets are fictional.

| Priority | Criteria | Target |
|---|---|---|
| urgent | Refund demand with a deadline, chargeback or legal threat; failed, lost, or damaged time-critical or high-value delivery; customer chased 2+ times | 1 hour |
| high | Refund request or late delivery without a deadline; double or wrong charge; service-failure complaint | 4 hours |
| normal | Status, tracking, invoice copy, address change, general questions | 1 business day |
| low | Thanks, feedback, newsletters, marketing, spam | 3 business days |

## Shape of the set

- 16 refund, 20 delivery, 14 billing, 12 complaint, 16 inquiry, 12 spam, 10 other
- 13 urgent, 32 high, 37 normal, 18 low
- 50 in `support`, 27 in `refunds`, 23 in `deliveries`
- The first 50 rows contain every category and priority, so they are a fair sample
  for the 50-email temperature experiment
- 11 bodies are HTML, and at least 30 plain bodies carry a signature or quoted
  reply so the email cleaner has real work to do

Per-category precision and recall on the smaller categories (10 to 12 emails)
rest on few examples, so treat them as indicative.
