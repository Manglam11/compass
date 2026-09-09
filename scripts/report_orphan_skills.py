"""Report skills that appear in zero role weight buckets.

Read-only: loads the taxonomy and prints, never modifies anything.

Run with: uv run python scripts/report_orphan_skills.py
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from compass.taxonomy.loader import WEIGHT_BUCKETS, load_taxonomy

TAXONOMY_DIR = Path(__file__).resolve().parent.parent / "taxonomy"


def main() -> int:
    skills_path = TAXONOMY_DIR / "skills.yaml"
    roles_path = TAXONOMY_DIR / "roles.yaml"

    taxonomy = load_taxonomy(skills_path, roles_path)

    used_skill_ids: set[str] = set()
    for role in taxonomy.roles.values():
        for bucket in WEIGHT_BUCKETS:
            used_skill_ids.update(getattr(role, bucket))

    orphans_by_family: dict[str, list[str]] = defaultdict(list)
    for skill in taxonomy.skills.values():
        if skill.id not in used_skill_ids:
            orphans_by_family[skill.family].append(skill.id)

    total = sum(len(ids) for ids in orphans_by_family.values())

    print(f"orphan skills (used in 0 role weight buckets): {total}")
    for family in sorted(orphans_by_family):
        ids = ", ".join(sorted(orphans_by_family[family]))
        print(f"  {family} ({len(orphans_by_family[family])}): {ids}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
