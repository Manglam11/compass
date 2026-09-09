"""Suspected-PII detection over already-extracted resume text.

Detects emails, phone numbers (international and Indian formats), LinkedIn
and GitHub profile URLs, and other http(s) URLs. Names are deliberately not
detected here — that is a manual review step.

Matches are found in priority order (email, linkedin, github, url, phone)
and are non-overlapping: once a span of text is claimed by a higher-priority
pattern it cannot also be reported under a lower-priority one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?", re.IGNORECASE
)

GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_-]+/?", re.IGNORECASE)

URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)

# Each phone alternative matches digits one at a time, each with an optional
# leading separator, so grouping style (spaces, dashes, dots, parens) never
# needs to be enumerated up front.
PHONE_RE = re.compile(
    r"(?:\+\d{1,3}(?:[\s().-]?\d){6,12})"  # international, e.g. +91 98765 43210
    r"|(?:(?<!\d)[6-9]\d(?:[\s-]?\d){8}(?!\d))"  # Indian mobile, 10 digits, no country code
    r"|(?:(?<!\d)\(?\d{3}\)?(?:[\s.-]?\d){7}(?!\d))"  # US-style, e.g. (415) 555-2671
)

PLACEHOLDER = {
    "email": "[EMAIL]",
    "phone": "[PHONE]",
    "linkedin": "[LINKEDIN]",
    "github": "[GITHUB]",
    "url": "[URL]",
}

_PATTERNS_IN_PRIORITY_ORDER = (
    ("email", EMAIL_RE),
    ("linkedin", LINKEDIN_RE),
    ("github", GITHUB_RE),
    ("url", URL_RE),
    ("phone", PHONE_RE),
)


@dataclass(frozen=True)
class PIIMatch:
    kind: str
    value: str
    start: int
    end: int


def _overlaps(span: tuple[int, int], consumed: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < c_end and end > c_start for c_start, c_end in consumed)


def find_pii(text: str) -> list[PIIMatch]:
    matches: list[PIIMatch] = []
    consumed: list[tuple[int, int]] = []

    for kind, pattern in _PATTERNS_IN_PRIORITY_ORDER:
        for m in pattern.finditer(text):
            span = m.span()
            if span[0] == span[1] or _overlaps(span, consumed):
                continue
            matches.append(PIIMatch(kind=kind, value=m.group(0), start=span[0], end=span[1]))
            consumed.append(span)

    matches.sort(key=lambda match: match.start)
    return matches
