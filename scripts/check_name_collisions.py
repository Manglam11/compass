"""Check per-resume names against the skill taxonomy for alias collisions.

If a name token exactly matches a skill alias, or is a substring of a
multi-word skill alias (e.g. "Carlo" vs. "Monte Carlo"), redacting that
name will also strip the skill mention from that resume — see
compass.resume_intake.collisions and the KNOWN LIMITATION note in
compass.resume_intake.names. This script only measures the problem; it
does not fix it. Names and matched tokens are never printed, only their
length, so this is safe to run and share output from.

Run with:
  uv run python scripts/check_name_collisions.py --names-file names.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from compass.resume_intake.collisions import find_collisions
from compass.resume_intake.names import NamesFileError, load_name_map
from compass.taxonomy.loader import TaxonomyError, load_taxonomy

TAXONOMY_DIR = Path(__file__).resolve().parent.parent / "taxonomy"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names-file", type=Path, required=True)
    parser.add_argument("--skills-file", type=Path, default=TAXONOMY_DIR / "skills.yaml")
    parser.add_argument("--roles-file", type=Path, default=TAXONOMY_DIR / "roles.yaml")
    args = parser.parse_args()

    try:
        name_map = load_name_map(args.names_file)
    except NamesFileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        taxonomy = load_taxonomy(args.skills_file, args.roles_file)
    except TaxonomyError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    collisions = find_collisions(name_map, taxonomy.alias_index)

    if not collisions:
        print("OK — no name/skill alias collisions found.")
        return 0

    for collision in collisions:
        print(
            f"{collision.resume_id} skill={collision.skill_id} "
            f"token_length={collision.token_length}"
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
