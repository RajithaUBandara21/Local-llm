import re
from html.parser import HTMLParser

_HTML_TAG = re.compile(r"</?(?:html|body|div|p|br|span|table|a|ul|li)(?:\s[^<>]*)?/?>", re.IGNORECASE)

# Content of these is not the sender's message; blockquote is dropped whole because
# converting Gmail-style quoted replies to text would lose their ">" markers.
_SKIPPED_TAGS = {"script", "style", "head", "blockquote"}
_LINE_BREAK_TAGS = {"br", "p", "div", "li", "tr", "table", "hr", "h1", "h2", "h3", "h4", "h5", "h6"}


def looks_like_html(text: str) -> bool:
    return _HTML_TAG.search(text) is not None


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1
        if tag in _LINE_BREAK_TAGS:
            self._parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        # A self-closing tag such as <br/> has no end tag, so it must not change skip depth.
        if tag in _LINE_BREAK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if tag in _LINE_BREAK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            # Source newlines are formatting, not line breaks; only the tags above make those.
            self._parts.append(re.sub(r"\s+", " ", data))

    def text(self) -> str:
        return "".join(self._parts)


def html_to_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    # Data was collapsed to single spaces already; tags can leave one at a line edge.
    return "\n".join(line.strip() for line in extractor.text().split("\n"))


_QUOTED_LINE = re.compile(r"^\s*>")
_ATTRIBUTION = re.compile(r"^\s*On\s.+\swrote:\s*$")
_ATTRIBUTION_START = re.compile(r"^\s*On\s")
_ATTRIBUTION_END = re.compile(r"(?:^|\s)wrote:\s*$")
_ORIGINAL_MESSAGE = re.compile(r"^\s*-{3,}\s*Original Message\s*-{3,}\s*$", re.IGNORECASE)
_HEADER_FROM = re.compile(r"^\s*From:", re.IGNORECASE)
_HEADER_SENT = re.compile(r"^\s*(Sent|Date):", re.IGNORECASE)
_HEADER_SUBJECT = re.compile(r"^\s*Subject:", re.IGNORECASE)
_SIGNATURE_DELIMITER = re.compile(r"^-- ?$")
_DEVICE_FOOTER = re.compile(r"^\s*(Sent from my |Get Outlook for )", re.IGNORECASE)
_CLOSING_PHRASE = re.compile(
    r"^\s*(regards|best regards|kind regards|warm regards|best|best wishes|thanks|thank you"
    r"|many thanks|sincerely|yours sincerely|yours faithfully|cheers)\s*[,!]?\s*$",
    re.IGNORECASE,
)

_OUTLOOK_HEADER_WINDOW = 5
_SIGNATURE_MAX_LINES = 6
_SIGNATURE_MAX_LINE_LENGTH = 60


def _is_outlook_header(lines: list[str], index: int) -> bool:
    if not _HEADER_FROM.match(lines[index]):
        return False
    window = lines[index + 1:index + 1 + _OUTLOOK_HEADER_WINDOW]
    return any(_HEADER_SENT.match(line) for line in window) and any(_HEADER_SUBJECT.match(line) for line in window)


def _cut_forwarded_history(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        if _ORIGINAL_MESSAGE.match(line) or _is_outlook_header(lines, index):
            return lines[:index]
    return lines


def _strip_quoted_replies(lines: list[str]) -> list[str]:
    lines = _cut_forwarded_history(lines)
    kept: list[str] = []
    skip_next = False
    for index, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
        if _QUOTED_LINE.match(line) or _ATTRIBUTION.match(line):
            continue
        # Mail clients wrap a long attribution so "wrote:" lands on the next line.
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if _ATTRIBUTION_START.match(line) and _ATTRIBUTION_END.search(next_line):
            skip_next = True
            continue
        kept.append(line)
    return kept


def _strip_device_footer(lines: list[str]) -> list[str]:
    last = len(lines)
    while last and not lines[last - 1].strip():
        last -= 1
    if last and _DEVICE_FOOTER.match(lines[last - 1]):
        return lines[:last - 1]
    return lines


def _cut_closing_signature(lines: list[str]) -> list[str]:
    closing = [i for i, line in enumerate(lines) if _CLOSING_PHRASE.match(line)]
    if not closing:
        return lines
    after = [line for line in lines[closing[-1] + 1:] if line.strip()]
    # A long tail means the phrase opened a real paragraph, not a sign-off block.
    if len(after) <= _SIGNATURE_MAX_LINES and all(len(line.strip()) <= _SIGNATURE_MAX_LINE_LENGTH for line in after):
        return lines[:closing[-1]]
    return lines


def _strip_signature(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        if _SIGNATURE_DELIMITER.match(line):
            lines = lines[:index]
            break
    return _cut_closing_signature(_strip_device_footer(lines))


def _tidy(lines: list[str]) -> str:
    text = "\n".join(line.rstrip() for line in lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_body(text: str, is_html: bool = False) -> str:
    if is_html:
        text = html_to_text(text)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return _tidy(_strip_signature(_strip_quoted_replies(lines)))
