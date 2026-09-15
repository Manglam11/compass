"""Shared resume-loading + rung-1/rung-2 extraction, used by both
scripts/rung_compare.py and scripts/rung_grounding.py so the two scripts
can't drift on how resumes are loaded and extracted.
"""

from __future__ import annotations

from pathlib import Path

from compass.extract import embeddings, gazetteer
from compass.resume_intake.text import extract_resume_text
from compass.taxonomy.models import Taxonomy


def load_resume_extractions(
    taxonomy: Taxonomy,
    files_by_key: dict[str, Path],
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, str]]:
    rung1_by_key: dict[str, set[str]] = {}
    rung2_by_key: dict[str, set[str]] = {}
    text_by_key: dict[str, str] = {}

    for key, path in files_by_key.items():
        try:
            text = extract_resume_text(path)
            rung1_by_key[key] = set(gazetteer.extract_skills(text, taxonomy))
            rung2_by_key[key] = set(embeddings.extract_skills(text, taxonomy))
            text_by_key[key] = text
        except Exception as exc:
            raise RuntimeError(f"failed to extract resume {key!r} ({path}): {exc}") from exc

    return rung1_by_key, rung2_by_key, text_by_key
