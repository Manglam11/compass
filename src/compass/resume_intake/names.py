"""Per-resume name mapping for redaction.

Names cannot be reliably pattern-detected, so they are supplied explicitly
via a --names-file mapping each resume to its own name(s):

    prac_001: Nick Miller
    exam_014: Priya Nair

One `<resume_id>: <name>` pair per line, UTF-8. Blank lines and lines
starting with # are ignored. `resume_id` must match `^(prac|exam)_\\d{3}$`
(the file stem used elsewhere in resume_intake, e.g. `prac_001.pdf`).

A resume_id absent from the file gets no name redaction at all — that is
valid, not an error, since some resumes have no name in the document body.
Each resume's compiled pattern is built and applied to that resume ONLY:
a name belonging to one person must never redact text in someone else's
resume, and common name tokens (e.g. "Black", "Alex") are frequent enough
in ordinary prose that a global list would corrupt unrelated documents for
zero privacy gain.

Within a single resume, matching is unchanged from the flat-list version:
each line's name is matched two ways — as the whole phrase, and as its
individual whitespace-separated parts, since resumes commonly refer to a
person by first name alone in prose ("Nick led the team"). Matching is
whole-word, case-insensitive, and longest-match-first (alternatives are
tried longest first at each position, so a two-word name is redacted as
one [NAME] span rather than two adjacent ones). A trailing possessive
("Miller's") is left untouched around the match for free: the apostrophe
is not a word character, so \\b already sits right before it.

KNOWN LIMITATION: a name that collides with a skill/technology token (e.g.
a person named "Django" or "Salesforce") will cause that token to be
redacted everywhere in *that person's own resume*, destroying that skill's
extraction there. This module does not attempt to resolve that collision —
it's an accepted tradeoff of matching names by literal text. Scoping the
mapping per resume (this module's whole point) at least prevents that
collision from bleeding into every other resume in the batch.
"""

from __future__ import annotations

import re
from pathlib import Path

RESUME_ID_RE = re.compile(r"^(prac|exam)_\d{3}$")


class NamesFileError(Exception):
    pass


def load_name_map(path: Path) -> dict[str, str]:
    """Parse a `<resume_id>: <name>` mapping file.

    Raises on a duplicate resume_id or a malformed line (missing colon,
    invalid resume_id, or empty name) — both name the offending line
    number or id so the file can be fixed. Does NOT check the ids against
    any directory on disk; use `unknown_resume_ids` for that, since only
    the caller knows which directory is in play.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise NamesFileError(f"names file not found: {path}") from exc
    except OSError as exc:
        raise NamesFileError(f"could not read names file {path}: {exc}") from exc

    mapping: dict[str, str] = {}
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if ":" not in stripped:
            raise NamesFileError(
                f"malformed line {lineno}: expected '<resume_id>: <name>', got {raw_line!r}"
            )

        resume_id, _, name = stripped.partition(":")
        resume_id = resume_id.strip()
        name = name.strip()

        if not RESUME_ID_RE.match(resume_id) or not name:
            raise NamesFileError(
                f"malformed line {lineno}: expected '<resume_id>: <name>', got {raw_line!r}"
            )

        if resume_id in mapping:
            raise NamesFileError(f"duplicate resume_id in names file: {resume_id}")

        mapping[resume_id] = name

    return mapping


def unknown_resume_ids(mapping: dict[str, str], known_ids: set[str]) -> list[str]:
    """resume_ids in `mapping` with no corresponding file on disk.

    Not an error — some batches simply don't include every id ever
    mentioned in a names file — but worth warning about since it usually
    means a stale entry or a typo.
    """
    return sorted(resume_id for resume_id in mapping if resume_id not in known_ids)


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


def compile_name_patterns(mapping: dict[str, str]) -> dict[str, re.Pattern[str]]:
    """Compile one pattern per resume_id, scoped to that resume only."""
    patterns: dict[str, re.Pattern[str]] = {}
    for resume_id, name in mapping.items():
        pattern = compile_name_pattern([name])
        if pattern is not None:
            patterns[resume_id] = pattern
    return patterns
