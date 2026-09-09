"""Explicit name-list redaction.

Names cannot be reliably pattern-detected, so they are supplied explicitly
via a --names-file: one name per line, UTF-8, blank lines and lines
starting with # ignored.

Each line is matched two ways: as the whole phrase, and as its individual
whitespace-separated parts, since resumes commonly refer to a person by
first name alone in prose ("Nick led the team"). Matching is whole-word,
case-insensitive, and longest-match-first (alternatives are tried longest
first at each position, so a two-word name is redacted as one [NAME] span
rather than two adjacent ones). A trailing possessive ("Miller's") is left
untouched around the match for free: the apostrophe is not a word
character, so \\b already sits right before it.

KNOWN LIMITATION: a name that collides with a skill/technology token (e.g.
a person named "Django" or "Salesforce") will cause that token to be
redacted everywhere in the document, destroying that skill's extraction
for that resume. This module does not attempt to resolve that collision —
it's an accepted tradeoff of matching names by literal text.
"""

from __future__ import annotations

import re
from pathlib import Path


class NamesFileError(Exception):
    pass


def load_names(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise NamesFileError(f"names file not found: {path}") from exc
    except OSError as exc:
        raise NamesFileError(f"could not read names file {path}: {exc}") from exc

    names: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        names.append(stripped)
    return names


def _phrase_pattern(phrase: str) -> str:
    tokens = phrase.split()
    return r"\s+".join(re.escape(token) for token in tokens)


def compile_name_pattern(names: list[str]) -> re.Pattern[str] | None:
    """Build a whole-word, case-insensitive, longest-match-first pattern.

    Each name contributes the full phrase plus each of its individual
    parts as separate alternatives. Alternatives are ordered longest-first
    so that, at any given starting position, the regex engine's
    first-alternative-wins behavior picks the longest one that matches
    there — the standard trick for leftmost-longest matching with
    alternation.
    """
    alternatives: set[str] = set()
    for name in names:
        alternatives.add(name)
        alternatives.update(name.split())
    alternatives.discard("")

    if not alternatives:
        return None

    ordered = sorted(alternatives, key=len, reverse=True)
    body = "|".join(_phrase_pattern(alt) for alt in ordered)
    return re.compile(rf"\b(?:{body})\b", re.IGNORECASE)
