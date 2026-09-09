"""Tests for the taxonomy file format, loader, and validator.

Failure cases use tmp_path fixtures with inline YAML — the real taxonomy/
files are never mutated.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from compass.taxonomy.loader import TaxonomyError, load_taxonomy
from compass.taxonomy.models import RolesFile, SkillsFile

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_SKILLS_PATH = REPO_ROOT / "taxonomy" / "skills.yaml"
REAL_ROLES_PATH = REPO_ROOT / "taxonomy" / "roles.yaml"

VALID_SKILLS_YAML = """
version: 0.1.0
skills:
  - id: docker
    display_name: Docker
    family: deployment
    aliases: [docker, dockerfile, dockerised, dockerized]
  - id: python
    display_name: Python
    family: language
    aliases: [python, python3, py]
"""

VALID_ROLES_YAML = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: ml_engineer
    display_name: ML Engineer
    core: {python: 3}
    supporting: {docker: 2}
    differentiator: {}
    min_core_ratio: 0.7
"""


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def write_pair(tmp_path: Path, skills_yaml: str, roles_yaml: str) -> tuple[Path, Path]:
    skills_path = write(tmp_path, "skills.yaml", skills_yaml)
    roles_path = write(tmp_path, "roles.yaml", roles_yaml)
    return skills_path, roles_path


def test_real_taxonomy_files_load_successfully():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    assert taxonomy.taxonomy_version == "0.3.0"
    assert {"docker", "python"} <= set(taxonomy.skills)
    assert "ml_engineer" in taxonomy.roles


def test_round_trip_load_dump_load_identical(tmp_path: Path):
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)

    skills_file = SkillsFile(
        version=taxonomy.taxonomy_version, skills=list(taxonomy.skills.values())
    )
    roles_file = RolesFile(
        version=taxonomy.taxonomy_version,
        taxonomy_version=taxonomy.taxonomy_version,
        roles=list(taxonomy.roles.values()),
    )

    skills_path = tmp_path / "skills.yaml"
    roles_path = tmp_path / "roles.yaml"
    skills_path.write_text(yaml.safe_dump(skills_file.model_dump()), encoding="utf-8")
    roles_path.write_text(yaml.safe_dump(roles_file.model_dump()), encoding="utf-8")

    reloaded = load_taxonomy(skills_path, roles_path)
    assert reloaded == taxonomy


def test_alias_index_maps_dockerised_to_docker():
    taxonomy = load_taxonomy(REAL_SKILLS_PATH, REAL_ROLES_PATH)
    assert taxonomy.alias_index["dockerised"] == "docker"


def test_duplicate_skill_id_rejected(tmp_path: Path):
    skills_yaml = """
version: 0.1.0
skills:
  - id: docker
    display_name: Docker
    family: deployment
    aliases: [docker]
  - id: docker
    display_name: Docker Two
    family: deployment
    aliases: [dockertwo]
"""
    roles_yaml = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: role_a
    display_name: Role A
    core: {docker: 3}
    min_core_ratio: 0.7
"""
    skills_path, roles_path = write_pair(tmp_path, skills_yaml, roles_yaml)
    with pytest.raises(TaxonomyError, match="duplicate skill id: 'docker'"):
        load_taxonomy(skills_path, roles_path)


def test_shared_alias_across_skills_names_both(tmp_path: Path):
    skills_yaml = """
version: 0.1.0
skills:
  - id: docker
    display_name: Docker
    family: deployment
    aliases: [docker, shared]
  - id: python
    display_name: Python
    family: language
    aliases: [python, shared]
"""
    roles_yaml = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: role_a
    display_name: Role A
    core: {docker: 3}
    min_core_ratio: 0.7
"""
    skills_path, roles_path = write_pair(tmp_path, skills_yaml, roles_yaml)
    with pytest.raises(TaxonomyError) as exc_info:
        load_taxonomy(skills_path, roles_path)
    message = str(exc_info.value)
    assert "shared" in message
    assert "docker" in message
    assert "python" in message


def test_role_references_unknown_skill_id(tmp_path: Path):
    roles_yaml = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: role_a
    display_name: Role A
    core: {nonexistent: 3}
    min_core_ratio: 0.7
"""
    skills_path, roles_path = write_pair(tmp_path, VALID_SKILLS_YAML, roles_yaml)
    with pytest.raises(TaxonomyError, match="unknown skill id: 'nonexistent'"):
        load_taxonomy(skills_path, roles_path)


def test_uppercase_alias_rejected(tmp_path: Path):
    skills_yaml = """
version: 0.1.0
skills:
  - id: docker
    display_name: Docker
    family: deployment
    aliases: [docker, Dockerfile]
"""
    roles_yaml = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: role_a
    display_name: Role A
    core: {docker: 3}
    min_core_ratio: 0.7
"""
    skills_path, roles_path = write_pair(tmp_path, skills_yaml, roles_yaml)
    with pytest.raises(TaxonomyError, match="non-lowercase"):
        load_taxonomy(skills_path, roles_path)


def test_skill_id_missing_from_own_aliases(tmp_path: Path):
    skills_yaml = """
version: 0.1.0
skills:
  - id: docker
    display_name: Docker
    family: deployment
    aliases: [dockerfile, dockerized]
"""
    roles_yaml = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: role_a
    display_name: Role A
    core: {docker: 3}
    min_core_ratio: 0.7
"""
    skills_path, roles_path = write_pair(tmp_path, skills_yaml, roles_yaml)
    with pytest.raises(TaxonomyError, match="missing its own id"):
        load_taxonomy(skills_path, roles_path)


def test_skill_in_core_and_supporting_rejected(tmp_path: Path):
    roles_yaml = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: role_a
    display_name: Role A
    core: {python: 3}
    supporting: {python: 2}
    min_core_ratio: 0.7
"""
    skills_path, roles_path = write_pair(tmp_path, VALID_SKILLS_YAML, roles_yaml)
    with pytest.raises(TaxonomyError, match="more than one weight bucket"):
        load_taxonomy(skills_path, roles_path)


def test_min_core_ratio_zero_rejected(tmp_path: Path):
    roles_yaml = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: role_a
    display_name: Role A
    core: {python: 3}
    min_core_ratio: 0.0
"""
    skills_path, roles_path = write_pair(tmp_path, VALID_SKILLS_YAML, roles_yaml)
    with pytest.raises(ValidationError):
        load_taxonomy(skills_path, roles_path)


def test_min_core_ratio_one_accepted(tmp_path: Path):
    roles_yaml = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: role_a
    display_name: Role A
    core: {python: 3}
    min_core_ratio: 1.0
"""
    skills_path, roles_path = write_pair(tmp_path, VALID_SKILLS_YAML, roles_yaml)
    taxonomy = load_taxonomy(skills_path, roles_path)
    assert taxonomy.roles["role_a"].min_core_ratio == 1.0


def test_version_mismatch_between_files(tmp_path: Path):
    roles_yaml = """
version: 0.2.0
taxonomy_version: 0.2.0
roles:
  - id: role_a
    display_name: Role A
    core: {python: 3}
    min_core_ratio: 0.7
"""
    skills_path, roles_path = write_pair(tmp_path, VALID_SKILLS_YAML, roles_yaml)
    with pytest.raises(TaxonomyError, match="does not match"):
        load_taxonomy(skills_path, roles_path)


def test_multiple_violations_reported_in_one_error(tmp_path: Path):
    skills_yaml = """
version: 0.1.0
skills:
  - id: docker
    display_name: Docker
    family: deployment
    aliases: [docker]
  - id: docker
    display_name: Docker Two
    family: deployment
    aliases: [dockertwo]
"""
    roles_yaml = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: role_a
    display_name: Role A
    core: {nonexistent: 3}
    min_core_ratio: 0.7
"""
    skills_path, roles_path = write_pair(tmp_path, skills_yaml, roles_yaml)
    with pytest.raises(TaxonomyError) as exc_info:
        load_taxonomy(skills_path, roles_path)
    message = str(exc_info.value)
    assert "duplicate skill id: 'docker'" in message
    assert "unknown skill id: 'nonexistent'" in message
