"""Validate taxonomy/skills.yaml + taxonomy/roles.yaml.

Run with: uv run python scripts/validate_taxonomy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from compass.taxonomy.loader import TaxonomyError, load_taxonomy

TAXONOMY_DIR = Path(__file__).resolve().parent.parent / "taxonomy"


def main() -> int:
    skills_path = TAXONOMY_DIR / "skills.yaml"
    roles_path = TAXONOMY_DIR / "roles.yaml"

    try:
        taxonomy = load_taxonomy(skills_path, roles_path)
    except TaxonomyError as exc:
        print(str(exc))
        return 1

    print(
        f"taxonomy {taxonomy.taxonomy_version} OK — "
        f"{len(taxonomy.skills)} skills, {len(taxonomy.roles)} roles"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
