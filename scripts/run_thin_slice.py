"""End-to-end thin slice: resume PDF in, ranked roles out. Rule-based only.

Run with: uv run python scripts/run_thin_slice.py <path-to-resume.pdf>
"""

from __future__ import annotations

import sys
from pathlib import Path

from compass.extract.pdf_text import InsufficientTextError
from compass.pipeline import analyse_resume


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: run_thin_slice.py <path-to-resume.pdf>")
        return 1

    resume_path = Path(argv[1])

    try:
        result = analyse_resume(resume_path)
    except InsufficientTextError as exc:
        print(f"error: {exc}")
        return 1

    print(f"extracted text: {result.character_count} characters")
    print()
    print(f"skills found ({len(result.found_skills)}): {', '.join(result.found_skills)}")
    print()
    print("matched roles:")
    for rank, role in enumerate(result.matched_roles, start=1):
        print(f"  {rank}. {role.role_id}  score={role.score:.3f}")
        print(f"     matched: {', '.join(role.matched_skills)}")
        print(f"     missing: {', '.join(role.missing_skills)}")
    print()
    print("excluded roles:")
    for excluded in result.excluded_roles:
        print(f"  {excluded.role_id}  reason={excluded.reason.value}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
