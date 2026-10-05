"""Whether a document is still good, and reading the dates that decide it. Pure — no DB, no LLM.

Validity is asked in three places (matching caps scores, readiness raises gaps, the evidence card
shows a note) and each had grown its own date parsing. One copy, so the three cannot disagree
about whether a certificate has lapsed.

`extract_dates` is the deliberate answer to a gap this product had from the start: expiry dates
were only ever what somebody typed into the upload form, so a certificate uploaded without one
looked permanent — and every expiry rule in the platform silently did nothing. The dates are
printed on the documents themselves. Reading them is regex over labelled lines rather than a
model: a certificate's dates are the last thing worth guessing at, and a wrong date here either
hides a blocker or invents one. Anything it finds is marked as read-from-document so a person
can confirm it (Rule 3 — the platform surfaces, a human ratifies).
"""
from __future__ import annotations

import re
from datetime import date, datetime

# Where a date came from. Stored on the document row.
SOURCE_MANUAL = "manual"      # a person typed it
SOURCE_DOCUMENT = "document"  # read off the document, not yet confirmed

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}

# "20 November 2026", "November 20, 2026", "2026-11-20", "20/11/2026"
_DATE_PATTERNS = (
    re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b"),
    re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b"),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"),
)

# The label that introduces a date, and what that date means. Ordered: the first match on a line
# wins, so "Initial Certification Date" cannot be read as the expiry.
_EXPIRY_LABELS = re.compile(
    r"(expiry\s+date|expires?\s+on|expires?|valid\s+(?:until|till|through|to)|"
    r"expiration\s+date|valid\s+up\s+to)\b",
    re.IGNORECASE,
)
_ISSUE_LABELS = re.compile(
    r"(issue\s+date|issued\s+on|date\s+of\s+issue|initial\s+certification\s+date|effective\s+date)\b",
    re.IGNORECASE,
)
# "Policy Period: 1 September 2025 to 31 August 2026" — a range whose end is the expiry.
_PERIOD_LABELS = re.compile(
    r"(policy\s+period|period\s+of\s+(?:insurance|cover|validity)|valid\s+from)\b",
    re.IGNORECASE,
)

_MAX_TEXT_CHARS = 20_000


def parse_date(value: object) -> date | None:
    """Accept an ISO date, an ISO timestamp, or a `date`. Anything else is None."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not value:
        return None
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def is_expired(document: dict, today: date) -> bool:
    """Has this document's expiry already passed? No recorded expiry means not expired."""
    expiry = parse_date(document.get("expiry_date"))
    return bool(expiry and expiry < today)


def expires_before(document: dict, cutoff: date | None) -> bool:
    """Would it have lapsed by `cutoff` — normally the tender's closing date?"""
    if cutoff is None:
        return False
    expiry = parse_date(document.get("expiry_date"))
    return bool(expiry and expiry < cutoff)


def _as_date(match: re.Match, pattern_index: int) -> date | None:
    try:
        if pattern_index == 0:
            day, month_name, year = match.group(1), match.group(2).lower(), match.group(3)
            month = _MONTHS.get(month_name)
            return date(int(year), month, int(day)) if month else None
        if pattern_index == 1:
            month_name, day, year = match.group(1).lower(), match.group(2), match.group(3)
            month = _MONTHS.get(month_name)
            return date(int(year), month, int(day)) if month else None
        if pattern_index == 2:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


def _dates_in(text: str) -> list[date]:
    found: list[date] = []
    for index, pattern in enumerate(_DATE_PATTERNS):
        for match in pattern.finditer(text):
            parsed = _as_date(match, index)
            if parsed:
                found.append(parsed)
    return found


def extract_dates(text: str) -> dict:
    """Read issue and expiry dates off a document's text.

    Only labelled dates count. A certificate is full of dates — assessment dates, project
    completion dates, a testimonial's date — and picking the largest or the last would be
    guesswork. The label is what makes it evidence.

    Returns ISO strings under `issue_date` / `expiry_date`, omitting whichever was not found.

    A label and its date are usually on one line, but the parser does not always keep them
    together: a key-value block it reads as a table comes back as HTML with one cell per line, so
    "Expiry Date:" and "20 November 2026" arrive on separate lines. That is how the CIDB
    certificate's expiry was missed while the insurance policy's — laid out as plain lines — was
    read. So tags are stripped first, and a label standing on its own line takes its date from the
    next line.
    """
    if not text:
        return {}
    lines = [line.strip(" \t|*:") for line in _clean(text[:_MAX_TEXT_CHARS]).splitlines()]
    lines = [line for line in lines if line]

    found: dict[str, str] = {}
    for index, line in enumerate(lines):
        dates = _dates_in(line)
        if not dates and _is_bare_label(line) and index + 1 < len(lines):
            following = lines[index + 1]
            # Only borrow the next line's date if that line is a bare value. A line with its own
            # colon is a labelled row with its own meaning ("Status as at 10 September 2026:
            # ACTIVE", "Expiry Date: ..." under a bare "Issue Date") and its date is not ours.
            if ":" not in following and not _is_bare_label(following):
                dates = _dates_in(following)
        if not dates:
            continue
        if "expiry_date" not in found and _EXPIRY_LABELS.search(line):
            found["expiry_date"] = dates[0].isoformat()
        elif "expiry_date" not in found and _PERIOD_LABELS.search(line) and len(dates) > 1:
            # A period runs from the earlier date to the later one; the later one is the expiry.
            found["expiry_date"] = max(dates).isoformat()
        if "issue_date" not in found and _ISSUE_LABELS.search(line):
            found["issue_date"] = dates[0].isoformat()
    return found


_TAG_RE = re.compile(r"<[^>]+>")
_MAX_BARE_LABEL_CHARS = 40


def _clean(text: str) -> str:
    """Drop HTML tags (keeping line structure) and decode entities like &nbsp;."""
    import html

    return html.unescape(_TAG_RE.sub(" ", text))


def _is_bare_label(line: str) -> bool:
    """A short line that is only a date label, e.g. "Expiry Date" — its value is on the next."""
    if len(line) > _MAX_BARE_LABEL_CHARS:
        return False
    return bool(_EXPIRY_LABELS.search(line) or _ISSUE_LABELS.search(line)
                or _PERIOD_LABELS.search(line))
