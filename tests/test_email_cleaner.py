from app.loaders.cleaner import clean_body, html_to_text, looks_like_html


def test_entities_are_decoded():
    assert html_to_text("<p>Fish &amp; chips&nbsp;now</p>").strip() == "Fish & chips now"


def test_script_and_style_content_is_removed():
    html = "<html><head><style>p {color: red}</style></head><body><script>alert(1)</script><p>Hello</p></body></html>"

    assert html_to_text(html).strip() == "Hello"


def test_br_and_p_give_separate_lines():
    lines = [line for line in html_to_text("<p>One</p><p>Two<br>Three</p>").split("\n") if line]

    assert lines == ["One", "Two", "Three"]


def test_blockquote_and_content_removed_while_earlier_paragraph_stays():
    html = "<p>My reply</p><blockquote><p>Original question</p></blockquote>"

    text = html_to_text(html)

    assert "My reply" in text
    assert "Original question" not in text


def test_link_keeps_text_and_not_url():
    text = html_to_text('<p>See <a href="https://example.com/x">our docs</a></p>')

    assert "our docs" in text
    assert "example.com" not in text


def test_source_whitespace_collapses_to_one_space():
    assert html_to_text("<p>a   \n\t b</p>").strip() == "a b"


def test_bare_less_than_is_not_html():
    assert looks_like_html("if a < b then stop") is False


def test_common_tags_are_html():
    assert looks_like_html("<div>hi</div>") is True
    assert looks_like_html("line one<br/>line two") is True


def test_quoted_lines_removed_at_any_depth_but_inline_reply_stays():
    text = "> first quoted\n>> deeper quote\nMy inline answer\n  > indented quote\nSecond answer"

    assert clean_body(text) == "My inline answer\nSecond answer"


def test_single_line_attribution_removed():
    text = "Thanks for the update.\n\nOn Mon, Mar 2, 2026 at 9:15 AM Jo <jo@example.com> wrote:\n> old text"

    assert clean_body(text) == "Thanks for the update."


def test_wrapped_attribution_removed():
    text = "Sounds good.\nOn Mon, Mar 2, 2026 at 9:15 AM Jo Smith <jo.smith@example.com>\nwrote:\n> old text"

    assert clean_body(text) == "Sounds good."


def test_original_message_and_everything_after_removed():
    text = "Please refund me.\n\n-----Original Message-----\nFrom: Shop\nSent: Monday\nSubject: Order\n\nYour order shipped."

    assert clean_body(text) == "Please refund me."


def test_outlook_header_block_and_everything_after_removed():
    text = "See my note below.\n\nFrom: Jo Smith\nSent: Monday, March 2, 2026 9:15 AM\nTo: Support\nSubject: Broken item\n\nOld text"

    assert clean_body(text) == "See my note below."


def test_lone_from_line_in_prose_stays():
    text = "Please check the order.\nFrom: the warehouse in Leeds\nIt never arrived."

    assert clean_body(text) == text


def test_double_dash_signature_cut():
    assert clean_body("Hello there.\n-- \nJo Smith\nAcme Ltd") == "Hello there."


def test_sign_off_with_short_name_block_cut():
    text = "Please call me back.\n\nBest regards,\nJo Smith\nSupport Lead\nAcme Ltd"

    assert clean_body(text) == "Please call me back."


def test_thanks_followed_by_long_tail_is_kept():
    tail = "\n".join(f"line {n}" for n in range(1, 8))
    text = f"Thanks,\n{tail}"

    assert clean_body(text) == text


def test_sign_off_with_a_long_line_after_is_kept():
    text = "Thanks,\n" + "x" * 61

    assert clean_body(text) == text


def test_final_device_footer_removed():
    assert clean_body("Running late today.\n\nSent from my iPhone") == "Running late today."


def test_entirely_quoted_body_returns_empty_string():
    assert clean_body("> old one\n> old two\n") == ""


def test_blank_line_runs_collapse_and_trailing_spaces_trimmed():
    assert clean_body("one   \n\n\n\n\ntwo\n\n") == "one\n\ntwo"


def test_crlf_and_cr_are_normalized():
    assert clean_body("one\r\ntwo\rthree") == "one\ntwo\nthree"


def test_html_body_is_converted_before_cleaning():
    html = "<div>Hello</div><div>Regards,</div><div>Jo</div>"

    assert clean_body(html, is_html=True) == "Hello"


def test_cleaning_is_idempotent_for_a_mixed_sample():
    sample = (
        "Hi team,\r\n\r\n> quoted line\r\nMy answer\r\n\r\n\r\n"
        "On Mon, Mar 2, 2026 Jo wrote:\r\n> older\r\n\r\nCheers,\r\nSam\r\n-- \r\nSam Lee"
    )

    once = clean_body(sample)

    assert once == "Hi team,\n\nMy answer"
    assert clean_body(once) == once
