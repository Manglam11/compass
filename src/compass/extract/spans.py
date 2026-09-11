"""Split resume text into line-level candidate spans for embedding.

Splitting is line-based only: no sentence segmentation, no noun-chunk
extraction. A line is dropped once it is too short (after stripping) to
carry enough signal for embedding similarity to be meaningful — this also
drops blank lines, which strip down to length zero.
"""

from __future__ import annotations

MIN_SPAN_LENGTH = 15


def split_into_spans(text: str) -> list[str]:
    spans = []
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) >= MIN_SPAN_LENGTH:
            spans.append(stripped)
    return spans
