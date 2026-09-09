"""Suspected-PII detection over already-extracted resume text.

Detects emails, phone numbers (international and Indian formats), LinkedIn
and GitHub profile URLs, other http(s) URLs, and a handful of narrower
classes added to close specific leaks found in review: mailto: targets,
domain-less LinkedIn/GitHub shorthand, and bare personal domains. Names
cannot be pattern-detected reliably; `find_pii` will also match names if
passed a compiled pattern from `compass.resume_intake.names`, built from an
explicit, human-supplied name list.

The narrower classes are kept as their own kinds (mailto, linkedin_shorthand,
github_shorthand, domain) rather than folded into the original email/
linkedin/github kinds, so that widening a pattern shows up as a new line in
scan output instead of silently inflating an existing count.

Matches are found in priority order and are non-overlapping: once a span of
text is claimed by a higher-priority pattern it cannot also be reported
under a lower-priority one. mailto is checked before email so a mailto:
target is reported once, as mailto, not twice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

MAILTO_RE = re.compile(r"mailto:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)

LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_-]+/?", re.IGNORECASE
)

# linkedin.com/<slug> without the /in/ segment, bare "linkedin/<slug>", and
# the bare "in/<slug>" shorthand LinkedIn itself uses for share links. The
# bare "in/<slug>" form is generic enough to collide with ordinary English
# ("...specializing in/around cloud...") so it's restricted to slugs that
# contain a digit or hyphen, which is how real profile slugs look.
LINKEDIN_SHORTHAND_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?!in/)[A-Za-z0-9_-]+/?"
    r"|(?:https?://)?(?:www\.)?linkedin/[A-Za-z0-9_-]+/?"
    r"|(?<![\w/.-])(?:www\.)?in/(?=[A-Za-z0-9_-]*[0-9-])[A-Za-z0-9_-]+\b",
    re.IGNORECASE,
)

GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_-]+/?", re.IGNORECASE)

GITHUB_SHORTHAND_RE = re.compile(r"(?:https?://)?(?:www\.)?github/[A-Za-z0-9_-]+/?", re.IGNORECASE)

URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)

# Bare "<name>.<tld>" with no scheme and no leading www — e.g. a personal
# site typed as "janedoe.dev" rather than "https://janedoe.dev". The tld
# list is deliberately short and doesn't overlap with common file
# extensions (.py, .js, .md, .csv, .json, .yaml, .txt, .pdf, .docx), and the
# name must start with a letter, so filenames and version strings like
# "3.11" can't match.
_DOMAIN_TLDS = ("com", "dev", "io", "tech", "me", "net", "org", "xyz", "in", "co")
DOMAIN_RE = re.compile(
    r"(?<![\w.@/])(?!www\.)[A-Za-z][A-Za-z0-9-]*\.(?:"
    + "|".join(_DOMAIN_TLDS)
    + r")(?![A-Za-z0-9-])",
    re.IGNORECASE,
)

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
    "mailto": "[EMAIL]",
    "linkedin_shorthand": "[LINKEDIN]",
    "github_shorthand": "[GITHUB]",
    "domain": "[URL]",
    "name": "[NAME]",
}

_PATTERNS_IN_PRIORITY_ORDER = (
    ("mailto", MAILTO_RE),
    ("email", EMAIL_RE),
    ("linkedin", LINKEDIN_RE),
    ("linkedin_shorthand", LINKEDIN_SHORTHAND_RE),
    ("github", GITHUB_RE),
    ("github_shorthand", GITHUB_SHORTHAND_RE),
    ("url", URL_RE),
    ("domain", DOMAIN_RE),
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


def find_pii(text: str, name_pattern: re.Pattern[str] | None = None) -> list[PIIMatch]:
    """Find suspected PII, plus explicit-listed names if `name_pattern` is given.

    Names are checked last (lowest priority): a span already claimed by an
    email/phone/url/etc. match cannot also be reported as a name.
    """
    matches: list[PIIMatch] = []
    consumed: list[tuple[int, int]] = []

    patterns = _PATTERNS_IN_PRIORITY_ORDER
    if name_pattern is not None:
        patterns = (*patterns, ("name", name_pattern))

    for kind, pattern in patterns:
        for m in pattern.finditer(text):
            span = m.span()
            if span[0] == span[1] or _overlaps(span, consumed):
                continue
            matches.append(PIIMatch(kind=kind, value=m.group(0), start=span[0], end=span[1]))
            consumed.append(span)

    matches.sort(key=lambda match: match.start)
    return matches
