from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.loaders.base import EmailLoadError
from app.loaders.csv_loader import CsvEmailLoader
from app.loaders.factory import get_email_loader
from app.loaders.mbox_loader import MboxEmailLoader
from app.schemas import LoadedEmail


def make_email(received_at):
    return LoadedEmail(sender="a@example.com", subject="Hi", body_clean="Body", received_at=received_at)


def test_aware_non_utc_datetime_becomes_same_instant_in_utc():
    ist = timezone(timedelta(hours=5, minutes=30))
    original = datetime(2026, 3, 2, 14, 45, tzinfo=ist)

    email = make_email(original)

    assert email.received_at == original
    assert email.received_at.utcoffset() == timedelta(0)
    assert email.received_at.hour == 9 and email.received_at.minute == 15


def test_naive_datetime_keeps_clock_time_as_utc():
    email = make_email(datetime(2026, 3, 2, 9, 15))

    assert email.received_at == datetime(2026, 3, 2, 9, 15, tzinfo=timezone.utc)
    assert email.received_at.tzinfo == timezone.utc


def test_none_received_at_stays_none():
    assert make_email(None).received_at is None


CSV_HEADER = "sender,subject,body,received_at\n"


def write_csv(tmp_path, text):
    path = tmp_path / "mail.csv"
    path.write_bytes(text.encode("utf-8"))
    return path


def test_csv_normal_file_loads_in_row_order(tmp_path):
    path = write_csv(
        tmp_path,
        CSV_HEADER
        + "a@example.com,First,Hello one,2026-03-02T09:15:00+00:00\n"
        + "b@example.com, Second ,Hello two,2026-03-02 10:00:00\n",
    )

    emails = CsvEmailLoader().load(path)

    assert [e.sender for e in emails] == ["a@example.com", "b@example.com"]
    assert [e.subject for e in emails] == ["First", "Second"]
    assert emails[0].received_at == datetime(2026, 3, 2, 9, 15, tzinfo=timezone.utc)
    assert emails[1].received_at == datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc)


def test_csv_bom_is_not_glued_to_first_header(tmp_path):
    path = write_csv(tmp_path, "\ufeff" + CSV_HEADER + "a@example.com,Hi,Body,\n")

    assert CsvEmailLoader().load(path)[0].sender == "a@example.com"


def test_csv_quoted_multiline_body_keeps_its_lines(tmp_path):
    path = write_csv(tmp_path, CSV_HEADER + 'a@example.com,Hi,"line one\nline two",\n')

    assert CsvEmailLoader().load(path)[0].body_clean == "line one\nline two"


def test_csv_html_body_is_converted(tmp_path):
    path = write_csv(tmp_path, CSV_HEADER + 'a@example.com,Hi,"<p>One</p><p>Two &amp; more</p>",\n')

    assert CsvEmailLoader().load(path)[0].body_clean == "One\n\nTwo & more"


def test_csv_extra_columns_are_ignored(tmp_path):
    path = write_csv(
        tmp_path,
        "sender,subject,body,received_at,category\n"
        "a@example.com,Hi,Body,,billing\n",
    )

    emails = CsvEmailLoader().load(path)

    assert emails[0].received_at is None


def test_csv_header_only_returns_empty_list(tmp_path):
    assert CsvEmailLoader().load(write_csv(tmp_path, CSV_HEADER)) == []


def test_csv_short_row_fills_missing_cells_with_empty_text(tmp_path):
    emails = CsvEmailLoader().load(write_csv(tmp_path, CSV_HEADER + "a@example.com,Hi\n"))

    assert emails[0].body_clean == ""
    assert emails[0].received_at is None


def test_csv_missing_file_raises_load_error(tmp_path):
    with pytest.raises(EmailLoadError, match="not found"):
        CsvEmailLoader().load(tmp_path / "nope.csv")


def test_csv_directory_path_raises_load_error(tmp_path):
    with pytest.raises(EmailLoadError):
        CsvEmailLoader().load(tmp_path)


def test_csv_undecodable_file_raises_load_error(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_bytes(b"sender,subject,body,received_at\n\xff\xfe\x00,x,y,\n")

    with pytest.raises(EmailLoadError, match="UTF-8"):
        CsvEmailLoader().load(path)


def test_csv_empty_file_raises_load_error(tmp_path):
    with pytest.raises(EmailLoadError, match="header"):
        CsvEmailLoader().load(write_csv(tmp_path, ""))


def test_csv_missing_columns_are_named(tmp_path):
    with pytest.raises(EmailLoadError, match="subject, received_at"):
        CsvEmailLoader().load(write_csv(tmp_path, "sender,body\na@example.com,Hi\n"))


def test_csv_bad_received_at_names_the_data_row(tmp_path):
    path = write_csv(tmp_path, CSV_HEADER + "a@example.com,Hi,Body,2026-03-02\nb@example.com,Hi,Body,yesterday\n")

    with pytest.raises(EmailLoadError, match="row 2"):
        CsvEmailLoader().load(path)


def write_mbox(tmp_path, *messages):
    # Bytes keep the line endings identical on every platform.
    text = "".join(f"From MAILER-DAEMON Mon Mar  2 09:15:00 2026\n{m.strip(chr(10))}\n\n" for m in messages)
    path = tmp_path / "mail.mbox"
    path.write_bytes(text.encode("utf-8"))
    return path


PLAIN_MESSAGE = """From: Jo Smith <jo@example.com>
Subject: Hello
Date: Mon, 2 Mar 2026 09:15:00 +0000

Body text"""


def test_mbox_two_messages_load_in_order(tmp_path):
    second = PLAIN_MESSAGE.replace("Jo Smith <jo@example.com>", "sam@example.com").replace("Hello", "Again")

    emails = MboxEmailLoader().load(write_mbox(tmp_path, PLAIN_MESSAGE, second))

    assert [e.sender for e in emails] == ["Jo Smith <jo@example.com>", "sam@example.com"]
    assert [e.subject for e in emails] == ["Hello", "Again"]
    assert emails[0].body_clean == "Body text"


def test_mbox_encoded_word_subject_and_sender_are_decoded(tmp_path):
    message = (
        "From: =?UTF-8?B?Sm9zw6k=?= <jose@example.com>\n"
        "Subject: =?UTF-8?B?Q2Fmw6k=?=\n"
        "\n"
        "Body"
    )

    loaded = MboxEmailLoader().load(write_mbox(tmp_path, message))[0]

    assert loaded.sender == "José <jose@example.com>"
    assert loaded.subject == "Café"


def test_mbox_multipart_alternative_uses_plain_part(tmp_path):
    message = """From: a@example.com
Subject: Alt
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="b1"

--b1
Content-Type: text/plain; charset=utf-8

Plain version
--b1
Content-Type: text/html; charset=utf-8

<p>HTML version</p>
--b1--"""

    assert MboxEmailLoader().load(write_mbox(tmp_path, message))[0].body_clean == "Plain version"


def test_mbox_html_only_message_is_converted(tmp_path):
    message = "From: a@example.com\nSubject: Html\nContent-Type: text/html; charset=utf-8\n\n<p>One</p><p>Two &amp; more</p>"

    assert MboxEmailLoader().load(write_mbox(tmp_path, message))[0].body_clean == "One\n\nTwo & more"


def test_mbox_attachment_only_message_has_empty_body(tmp_path):
    message = """From: a@example.com
Subject: File
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="b1"

--b1
Content-Type: application/pdf
Content-Disposition: attachment; filename="a.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQK
--b1--"""

    emails = MboxEmailLoader().load(write_mbox(tmp_path, message))

    assert len(emails) == 1
    assert emails[0].body_clean == ""


def test_mbox_quoted_reply_and_signature_are_removed(tmp_path):
    message = "From: a@example.com\nSubject: Re: Hi\n\nMy answer\n\nOn Mon, Jo wrote:\n> old text\n-- \nSam Lee"

    assert MboxEmailLoader().load(write_mbox(tmp_path, message))[0].body_clean == "My answer"


def test_mbox_date_offset_is_stored_as_utc(tmp_path):
    message = PLAIN_MESSAGE.replace("+0000", "+0530")

    received_at = MboxEmailLoader().load(write_mbox(tmp_path, message))[0].received_at

    assert received_at == datetime(2026, 3, 2, 9, 15, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert received_at.utcoffset() == timedelta(0)
    assert received_at.hour == 3 and received_at.minute == 45


def test_mbox_missing_date_gives_none_and_missing_headers_give_empty_text(tmp_path):
    loaded = MboxEmailLoader().load(write_mbox(tmp_path, "X-Other: 1\n\nBody"))[0]

    assert loaded.received_at is None
    assert loaded.sender == ""
    assert loaded.subject == ""


def test_mbox_missing_file_raises_load_error(tmp_path):
    with pytest.raises(EmailLoadError, match="not found"):
        MboxEmailLoader().load(tmp_path / "nope.mbox")


def test_mbox_directory_path_raises_load_error(tmp_path):
    with pytest.raises(EmailLoadError):
        MboxEmailLoader().load(tmp_path)


def test_mbox_non_empty_file_without_messages_raises_load_error(tmp_path):
    path = tmp_path / "notes.mbox"
    path.write_bytes(b"just some text\nno mbox separators here\n")

    with pytest.raises(EmailLoadError, match="No messages"):
        MboxEmailLoader().load(path)


def test_mbox_empty_file_loads_no_emails(tmp_path):
    path = tmp_path / "empty.mbox"
    path.write_bytes(b"")

    assert MboxEmailLoader().load(path) == []


def test_mbox_unparseable_date_names_the_message(tmp_path):
    bad = PLAIN_MESSAGE.replace("Mon, 2 Mar 2026 09:15:00 +0000", "sometime last week")

    with pytest.raises(EmailLoadError, match="message 2"):
        MboxEmailLoader().load(write_mbox(tmp_path, PLAIN_MESSAGE, bad))


def test_mbox_undecodable_body_names_the_message(tmp_path):
    bad = "From: a@example.com\nSubject: Odd\nContent-Type: text/plain; charset=no-such-charset\n\nBody"

    with pytest.raises(EmailLoadError, match="message 2"):
        MboxEmailLoader().load(write_mbox(tmp_path, PLAIN_MESSAGE, bad))


def test_mbox_extension_gives_mbox_loader():
    assert isinstance(get_email_loader(Path("inbox.mbox")), MboxEmailLoader)


def test_csv_extension_gives_csv_loader():
    assert isinstance(get_email_loader(Path("inbox.csv")), CsvEmailLoader)


def test_extension_is_compared_case_insensitively():
    assert isinstance(get_email_loader(Path("INBOX.CSV")), CsvEmailLoader)
    assert isinstance(get_email_loader(Path("INBOX.Mbox")), MboxEmailLoader)


def test_unsupported_extension_names_the_supported_ones():
    with pytest.raises(EmailLoadError, match=r"\.csv, \.mbox"):
        get_email_loader(Path("notes.txt"))


def test_path_without_extension_is_unsupported():
    with pytest.raises(EmailLoadError):
        get_email_loader(Path("inbox"))
