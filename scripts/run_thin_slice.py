"""End-to-end thin slice: resume PDF in, ranked roles out. Rule-based only.

Run with: uv run python scripts/run_thin_slice.py <path-to-resume.pdf>
"""

from __future__ import annotations

import sys
from pathlib import Path

from compass.extract.gazetteer import extract_skills
from compass.extract.pdf_text import InsufficientTextError, extract_text
from compass.match.scorer import score_roles
from compass.taxonomy.loader import load_taxonomy

TAXONOMY_DIR = Path(__file__).resolve().parent.parent / "taxonomy"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: run_thin_slice.py <path-to-resume.pdf>")
        return 1

    resume_path = Path(argv[1])

    try:
        text = extract_text(resume_path)
    except InsufficientTextError as exc:
        print(f"error: {exc}")
        return 1

    taxonomy = load_taxonomy(TAXONOMY_DIR / "skills.yaml", TAXONOMY_DIR / "roles.yaml")
    found_skills = extract_skills(text, taxonomy)
    result = score_roles(found_skills, taxonomy)

    print(f"extracted text: {len(text)} characters")
    print()
    print(f"skills found ({len(found_skills)}): {', '.join(found_skills)}")
    print()
    print("matched roles:")
    for rank, role in enumerate(result.matched, start=1):
        print(f"  {rank}. {role.role_id}  score={role.score:.3f}")
        print(f"     matched: {', '.join(role.matched_skills)}")
        print(f"     missing: {', '.join(role.missing_skills)}")
    print()
    print("excluded roles:")
    for excluded in result.excluded:
        print(f"  {excluded.role_id}  reason={excluded.reason.value}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
