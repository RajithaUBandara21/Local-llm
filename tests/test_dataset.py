import csv
from collections import Counter
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path

import pytest

from app.loaders.cleaner import clean_body, looks_like_html
from app.loaders.factory import get_email_loader

DATASET = Path(__file__).resolve().parent.parent / "data" / "northport_emails.csv"

# Kept here until feature 18 defines the real enums.
CATEGORIES = {"refund", "delivery", "billing", "complaint", "inquiry", "spam", "other"}
PRIORITIES = {"urgent", "high", "normal", "low"}
MAILBOXES = {"support", "refunds", "deliveries"}

RESERVED_DOMAINS = {"example.com", "example.org", "example.net"}
RESERVED_SUFFIXES = (".example", ".test", ".invalid")

MIN_CLEAN_BODY_LENGTH = 15

EXPECTED_ROWS = 100
# Floors keep per-category precision and recall (feature 22) from resting on a handful of emails.
MIN_ROWS_PER_LABEL = 8
MIN_NON_SPAM_LOW = 5
MIN_ROWS_PER_MAILBOX = 20
# Enough raw mail shapes that the feature 16 cleaner is really exercised.
MIN_HTML_BODIES = 10
MIN_PLAIN_BODIES_WITH_NOISE = 30


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    with DATASET.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


@pytest.fixture(scope="module")
def emails():
    return get_email_loader(DATASET).load(DATASET)


def test_file_has_rows(rows):
    assert rows


def test_loader_returns_one_email_per_row_in_order(rows, emails):
    assert len(emails) == len(rows)
    assert [email.subject for email in emails] == [row["subject"].strip() for row in rows]


def test_ids_are_the_zero_padded_row_number(rows):
    assert [row["id"] for row in rows] == [f"E{number:03d}" for number in range(1, len(rows) + 1)]


def test_labels_use_allowed_values(rows):
    for row in rows:
        assert row["category"] in CATEGORIES, f"{row['id']} has category {row['category']!r}"
        assert row["priority"] in PRIORITIES, f"{row['id']} has priority {row['priority']!r}"


def test_mailbox_is_one_of_the_three(rows):
    for row in rows:
        assert row["mailbox"] in MAILBOXES, f"{row['id']} has mailbox {row['mailbox']!r}"


def test_spam_is_always_low_priority(rows):
    for row in rows:
        if row["category"] == "spam":
            assert row["priority"] == "low", f"{row['id']} is spam but {row['priority']}"


def is_reserved_domain(domain: str) -> bool:
    return domain in RESERVED_DOMAINS or domain.endswith(RESERVED_SUFFIXES)


def test_senders_are_plain_addresses_on_reserved_domains(rows):
    for row in rows:
        address = parseaddr(row["sender"])[1]
        assert address == row["sender"], f"{row['id']} sender is not a plain address"
        domain = address.rpartition("@")[2].lower()
        assert is_reserved_domain(domain), f"{row['id']} uses non-reserved domain {domain!r}"


def test_received_at_has_an_explicit_offset(rows):
    for row in rows:
        received_at = datetime.fromisoformat(row["received_at"])
        assert received_at.tzinfo is not None, f"{row['id']} received_at has no offset"


def test_cleaned_bodies_keep_real_content(rows, emails):
    for row, email in zip(rows, emails):
        assert len(email.body_clean) >= MIN_CLEAN_BODY_LENGTH, f"{row['id']} cleans down to {email.body_clean!r}"


def test_first_fifty_rows_cover_every_category_and_priority(rows):
    # The temperature experiment (feature 22) runs on 50 emails, so they must be a fair sample.
    first_fifty = rows[:50]
    assert {row["category"] for row in first_fifty} == CATEGORIES
    assert {row["priority"] for row in first_fifty} == PRIORITIES


def test_no_two_emails_share_a_body(rows):
    bodies = [row["body"] for row in rows]
    assert len(set(bodies)) == len(bodies)


def test_dataset_has_exactly_one_hundred_emails(rows):
    assert len(rows) == EXPECTED_ROWS


@pytest.mark.parametrize("field, allowed", [("category", CATEGORIES), ("priority", PRIORITIES)])
def test_every_label_value_has_enough_examples(rows, field, allowed):
    counts = Counter(row[field] for row in rows)
    for value in allowed:
        assert counts[value] >= MIN_ROWS_PER_LABEL, f"only {counts[value]} rows have {field} {value!r}"


def test_low_priority_is_not_only_spam(rows):
    non_spam_low = [row for row in rows if row["priority"] == "low" and row["category"] != "spam"]
    assert len(non_spam_low) >= MIN_NON_SPAM_LOW


def test_every_mailbox_has_enough_emails(rows):
    counts = Counter(row["mailbox"] for row in rows)
    for mailbox in MAILBOXES:
        assert counts[mailbox] >= MIN_ROWS_PER_MAILBOX, f"only {counts[mailbox]} rows in {mailbox!r}"


def test_dataset_has_html_bodies(rows):
    assert sum(looks_like_html(row["body"]) for row in rows) >= MIN_HTML_BODIES


def test_plain_bodies_carry_signatures_and_quoted_replies(rows):
    def loses_text(body: str) -> bool:
        return len("".join(clean_body(body).split())) < len("".join(body.split()))

    plain = [row["body"] for row in rows if not looks_like_html(row["body"])]
    assert sum(loses_text(body) for body in plain) >= MIN_PLAIN_BODIES_WITH_NOISE
