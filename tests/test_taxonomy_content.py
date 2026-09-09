"""Content checks for the real taxonomy/skills.yaml vocabulary (B2.1)."""

from __future__ import annotations

from pathlib import Path

from compass.taxonomy.loader import load_taxonomy

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_SKILLS_PATH = REPO_ROOT / "taxonomy" / "skills.yaml"
REAL_ROLES_PATH = REPO_ROOT / "taxonomy" / "roles.yaml"

ALLOWED_FAMILIES = {"language", "data", "ml", "deployment", "cloud", "automation", "practice"}

EXPECTED_SKILL_COUNT = 61


def test_real_skills_yaml_has_expected_skill_count():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    print(f"skill count: {len(taxonomy.skills)}")
    assert len(taxonomy.skills) == EXPECTED_SKILL_COUNT


def test_every_family_is_in_allowed_set():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    for skill in taxonomy.skills.values():
        assert skill.family in ALLOWED_FAMILIES


def test_alias_index_contains_expected_resume_phrasings():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    for alias in ("sklearn", "postgres", "ci/cd", "seaborn", "langchain"):
        assert alias in taxonomy.alias_index


def test_no_alias_belongs_to_two_different_skills():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    owner_by_alias: dict[str, str] = {}
    for skill in taxonomy.skills.values():
        for alias in skill.aliases:
            assert alias not in owner_by_alias, (
                f"alias '{alias}' owned by both '{owner_by_alias.get(alias)}' and '{skill.id}'"
            )
            owner_by_alias[alias] = skill.id
