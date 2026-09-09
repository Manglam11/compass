"""Build provenance rows for resumes on disk.

Fills only what can be read off the actual files (resume_id, format).
Source URLs were never recorded at collection time and are unrecoverable —
callers must not invent them.
"""

from __future__ import annotations

from pathlib import Path

PROVENANCE_HEADER = [
    "resume_id",
    "source_url",
    "retrieved_at",
    "format",
    "layout_bin",
    "anonymised",
    "notes",
]

RESUME_EXTENSIONS = {".pdf", ".docx"}

UNKNOWN_SOURCE = "unknown"


def build_provenance_rows(directory: Path) -> list[list[str]]:
    """Return one row per resume file in directory, sorted by resume_id.

    Every column beyond resume_id/format is left blank rather than guessed;
    source_url is always UNKNOWN_SOURCE since it cannot be recovered.
    """
    paths = [p for p in directory.iterdir() if p.suffix.lower() in RESUME_EXTENSIONS]
    paths.sort(key=lambda p: p.stem)
    return [[p.stem, UNKNOWN_SOURCE, "", p.suffix.lower().lstrip("."), "", "", ""] for p in paths]
