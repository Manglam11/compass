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


def test_gazetteer_finds_rest_api_from_framework_phrasing():
    skills = extract_skills("Built REST endpoints for the internal service.", TAXONOMY)
    assert "rest_api" in skills


def test_gazetteer_finds_linux_from_shell_on_ubuntu():
    # Not "bash script": 'bash' is already a separate skill id (see B3.0c
    # report), so it can't also be a linux alias without breaking global
    # alias uniqueness. 'shell'/'ubuntu' are the new linux aliases instead.
    skills = extract_skills("Automated tasks using the shell on Ubuntu servers.", TAXONOMY)
    assert "linux" in skills


def test_gazetteer_finds_vector_db_from_qdrant_vector_store():
    skills = extract_skills("Deployed Qdrant vector store for embeddings.", TAXONOMY)
    assert "vector_db" in skills


def test_gazetteer_finds_agent_frameworks_from_langgraph_agent_loop():
    skills = extract_skills("Implemented a LangGraph agent loop for task planning.", TAXONOMY)
    assert "agent_frameworks" in skills


def test_gazetteer_finds_etl_from_alembic_migration():
    skills = extract_skills("Managed schema changes with Alembic migration scripts.", TAXONOMY)
    assert "etl" in skills


def test_gazetteer_tensorflow_does_not_fire_without_tensorflow_mention():
    skills = extract_skills("Used TF-IDF and Keras for text classification.", TAXONOMY)
    assert "tensorflow" not in skills


def test_gazetteer_mlops_fires_on_bare_section_heading():
    # mlops aliases were left unchanged (see B3.0c report); a bare heading
    # still fires since alias matching cannot distinguish it from prose.
    skills = extract_skills("MLOps & Serving", TAXONOMY)
    assert "mlops" in skills
