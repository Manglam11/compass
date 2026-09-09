"""Extract text from a resume PDF.

A scanned PDF with no text layer must fail loudly rather than silently
produce an empty (or near-empty) string that looks like a candidate with
no skills.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

MIN_CHARACTERS = 100


class InsufficientTextError(Exception):
    pass


def extract_text(path: Path) -> str:
    with pymupdf.open(path) as doc:
        pages = [page.get_text() for page in doc]
    text = "\n".join(pages)

    if len(text) < MIN_CHARACTERS:
        raise InsufficientTextError(
            f"extracted only {len(text)} characters from '{path}' "
            f"(minimum {MIN_CHARACTERS}) — likely a scanned PDF with no text layer"
        )

    return text
