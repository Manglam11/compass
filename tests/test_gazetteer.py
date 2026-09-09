"""Tests for compass.extract.gazetteer."""

from __future__ import annotations

from pathlib import Path

from compass.extract.gazetteer import extract_skills
from compass.taxonomy.loader import load_taxonomy

REPO_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = load_taxonomy(
    REPO_ROOT / "taxonomy" / "skills.yaml", REPO_ROOT / "taxonomy" / "roles.yaml"
)


def test_gazetteer_finds_docker_from_dockerised():
    skills = extract_skills("Dockerised the pipeline for deployment.", TAXONOMY)
    assert "docker" in skills


def test_gazetteer_is_case_insensitive():
    skills = extract_skills("Experience with PYTHON and PostgreSQL.", TAXONOMY)
    assert "python" in skills
    assert "postgresql" in skills


def test_gazetteer_returns_sorted_deduplicated_ids():
    skills = extract_skills("Python python PYTHON, also used Docker and docker.", TAXONOMY)
    assert skills == sorted(set(skills))
    assert skills.count("python") == 1
    assert skills.count("docker") == 1
