"""Single entry point chaining extraction, skill matching, and role scoring.

Both the CLI (scripts/run_thin_slice.py) and the Streamlit UI go through
analyse_resume so they can never disagree about what a resume produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from compass.extract.gazetteer import extract_skills
from compass.extract.pdf_text import extract_text
from compass.match.scorer import ExcludedRole, RoleResult, ScoreResult, score_roles
from compass.taxonomy.loader import load_taxonomy

TAXONOMY_DIR = Path(__file__).resolve().parent.parent.parent / "taxonomy"


@dataclass(frozen=True)
class AnalysisResult:
    character_count: int
    found_skills: list[str]
    matched_roles: list[RoleResult]
    excluded_roles: list[ExcludedRole]


def analyse_resume(path: Path) -> AnalysisResult:
    text = extract_text(path)

    taxonomy = load_taxonomy(TAXONOMY_DIR / "skills.yaml", TAXONOMY_DIR / "roles.yaml")
    found_skills = extract_skills(text, taxonomy)
    result: ScoreResult = score_roles(found_skills, taxonomy)

    return AnalysisResult(
        character_count=len(text),
        found_skills=found_skills,
        matched_roles=result.matched,
        excluded_roles=result.excluded,
    )
