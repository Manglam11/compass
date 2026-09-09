"""Content checks for the real taxonomy/skills.yaml and roles.yaml (B2.1, B2.2)."""

from __future__ import annotations

from pathlib import Path

from compass.match.scorer import score_roles
from compass.taxonomy.loader import WEIGHT_BUCKETS, load_taxonomy

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_SKILLS_PATH = REPO_ROOT / "taxonomy" / "skills.yaml"
REAL_ROLES_PATH = REPO_ROOT / "taxonomy" / "roles.yaml"

ALLOWED_FAMILIES = {
    "language",
    "data",
    "ml",
    "genai",
    "deployment",
    "cloud",
    "automation",
    "practice",
}

EXPECTED_SKILL_COUNT = 59
EXPECTED_ROLE_COUNT = 8


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


def test_real_roles_yaml_has_exactly_eight_roles():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    print(f"role count: {len(taxonomy.roles)}")
    assert len(taxonomy.roles) == EXPECTED_ROLE_COUNT


def test_every_role_has_a_core_of_one_to_four_skills():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    for role in taxonomy.roles.values():
        assert 1 <= len(role.core) <= 4, f"role '{role.id}' has {len(role.core)} core skills"


def test_every_role_skill_id_exists_in_skills_yaml():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    known_skill_ids = set(taxonomy.skills)
    for role in taxonomy.roles.values():
        for bucket in WEIGHT_BUCKETS:
            for skill_id in getattr(role, bucket):
                assert skill_id in known_skill_ids, (
                    f"role '{role.id}' bucket '{bucket}' references unknown skill '{skill_id}'"
                )


def test_every_min_core_ratio_is_between_half_and_eighty_percent():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    for role in taxonomy.roles.values():
        assert 0.5 <= role.min_core_ratio <= 0.8, (
            f"role '{role.id}' has min_core_ratio {role.min_core_ratio}"
        )


def test_backend_developer_core_gate_clears_with_python_postgresql_docker():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    result = score_roles(["python", "postgresql", "docker"], taxonomy)

    matched_ids = {role.role_id for role in result.matched}
    excluded_ids = {excluded.role_id for excluded in result.excluded}
    assert "backend_developer" in matched_ids
    assert "backend_developer" not in excluded_ids


def test_backend_developer_core_gate_fails_with_python_postgresql_only():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    result = score_roles(["python", "postgresql"], taxonomy)

    matched_ids = {role.role_id for role in result.matched}
    excluded_ids = {excluded.role_id for excluded in result.excluded}
    assert "backend_developer" not in matched_ids
    assert "backend_developer" in excluded_ids
