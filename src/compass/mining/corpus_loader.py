"""Loads the raw labeled resume corpus (corpus/UpdatedResumeDataSet.csv) used
for alias mining: finding skill phrasings the taxonomy's existing aliases
don't cover yet.

This corpus is a CSV with columns Category, Resume. Its text underwent an
encode/decode round trip through cp1252 at some point before it reached us
(UTF-8 bytes decoded as cp1252, then re-encoded and, in places, decoded as
cp1252 a second time), producing mojibake like "NaÃƒÂ¯ve" for "Naïve".
_fix_mojibake reverses that by re-encoding as cp1252 and decoding as UTF-8,
repeating while that keeps changing the text and stays a valid decode.

ftfy is not a dependency of this project, so this fixer is deliberately
narrow: it only reverses the cp1252-as-UTF-8 round trip and gives up
(leaving the text untouched) on anything else. A meaningful fraction of rows
in this specific corpus contain literal U+FFFD replacement characters
(observed at the raw-file level, e.g. around bullet points) — that is
genuine data loss from whatever produced the CSV, and no decode/encode
round trip can recover it. Those rows will still contain \\ufffd after
load_corpus; this is a known, unfixed limitation of this corpus, not a bug
in the fixer.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

_MAX_MOJIBAKE_PASSES = 4


@dataclass
class CorpusResume:
    resume_id: str
    category: str
    text: str


def _fix_mojibake(text: str) -> str:
    for _ in range(_MAX_MOJIBAKE_PASSES):
        try:
            candidate = text.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if candidate == text:
            break
        text = candidate
    return text


def load_corpus(path: Path) -> list[CorpusResume]:
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    width = max(4, len(str(len(rows) - 1))) if rows else 4
    return [
        CorpusResume(
            resume_id=str(i).zfill(width),
            category=row["Category"],
            text=_fix_mojibake(row["Resume"]),
        )
        for i, row in enumerate(rows)
    ]


def batch_resumes(
    resumes: list[CorpusResume], batch_size: int = 10
) -> list[list[CorpusResume]]:
    return [resumes[i : i + batch_size] for i in range(0, len(resumes), batch_size)]
