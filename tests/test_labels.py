"""Tests for the resume label schema, loader, and validator.

All fixtures (taxonomy and label files) are inline YAML written to tmp_path —
no sample or example label files are committed to the repo.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from compass.labels.loader import LabelError, load_labels
from compass.taxonomy.loader import load_taxonomy

TAXONOMY_SKILLS_YAML = """
version: 0.1.0
skills:
  - id: python
    display_name: Python
    family: language
    aliases: [python, python3, py]
    description: Writing application code, automation scripts, and data pipelines.
  - id: docker
    display_name: Docker
    family: deployment
    aliases: [docker, dockerfile]
    description: Building and running containers to package and ship applications.
"""

TAXONOMY_ROLES_YAML = """
version: 0.1.0
taxonomy_version: 0.1.0
roles:
  - id: ml_engineer
    display_name: ML Engineer
    core: {python: 3}
    supporting: {docker: 2}
    differentiator: {}
    min_core_ratio: 0.7
  - id: data_analyst
    display_name: Data Analyst
    core: {python: 2}
    min_core_ratio: 0.6
"""

SHA_A = "a" * 64
SHA_B = "b" * 64


def make_taxonomy(tmp_path: Path):
    skills_path = tmp_path / "tax_skills.yaml"
    roles_path = tmp_path / "tax_roles.yaml"
    skills_path.write_text(TAXONOMY_SKILLS_YAML, encoding="utf-8")
    roles_path.write_text(TAXONOMY_ROLES_YAML, encoding="utf-8")
    return load_taxonomy(skills_path, roles_path)


def write_label(directory: Path, subdir: str, file_name: str, content: str) -> Path:
    target_dir = directory / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / file_name
    path.write_text(content, encoding="utf-8")
    return path


def valid_label(**overrides) -> str:
    fields = {
        "resume_id": "prac_001",
        "set": "practice",
        "status": "final",
        "sha": SHA_A,
        "file_name": "prac_001.pdf",
        "taxonomy_version": "0.1.0",
        "skills_present": "[python]",
        "skills_ambiguous": "[]",
        "roles_fit": "[ml_engineer]",
        "roles_should_exclude": "[]",
    }
    fields.update(overrides)
    return f"""
label_version: 1
resume_id: {fields["resume_id"]}
set: {fields["set"]}
source: self
status: {fields["status"]}
file_name: {fields["file_name"]}
file_sha256: "{fields["sha"]}"
format: pdf
layout: single_column
taxonomy_version: {fields["taxonomy_version"]}
labeller: manglam
labelled_at: 2026-01-15
skills_present: {fields["skills_present"]}
skills_ambiguous: {fields["skills_ambiguous"]}
roles_fit: {fields["roles_fit"]}
roles_should_exclude: {fields["roles_should_exclude"]}
notes: ""
"""


def test_valid_label_passes(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(labels_dir, "practice", "prac_001.yaml", valid_label())

    labels = load_labels(labels_dir, taxonomy=taxonomy)

    assert len(labels) == 1
    assert labels[0].resume_id == "prac_001"
    assert labels[0].skills_present == ["python"]
    assert labels[0].roles_fit == ["ml_engineer"]


def test_schema_violation_collected(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(
        labels_dir,
        "practice",
        "prac_001.yaml",
        valid_label(skills_present="[]", status="final"),
    )

    with pytest.raises(LabelError) as exc_info:
        load_labels(labels_dir, taxonomy=taxonomy)
    message = str(exc_info.value)
    assert "schema violation" in message
    assert "prac_001.yaml" in message


def test_draft_label_allows_empty_skills_present(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(
        labels_dir,
        "practice",
        "prac_001.yaml",
        valid_label(skills_present="[]", status="draft"),
    )

    labels = load_labels(labels_dir, taxonomy=taxonomy)

    assert len(labels) == 1
    assert labels[0].status == "draft"
    assert labels[0].skills_present == []


def test_require_final_rejects_draft_label(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(
        labels_dir,
        "practice",
        "prac_001.yaml",
        valid_label(skills_present="[]", status="draft"),
    )

    with pytest.raises(LabelError, match="label status is 'draft', final labels required"):
        load_labels(labels_dir, taxonomy=taxonomy, require_final=True)


def test_require_final_accepts_final_label(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(labels_dir, "practice", "prac_001.yaml", valid_label(status="final"))

    labels = load_labels(labels_dir, taxonomy=taxonomy, require_final=True)

    assert len(labels) == 1
    assert labels[0].status == "final"


def test_unknown_skill_id_rejected(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(
        labels_dir, "practice", "prac_001.yaml", valid_label(skills_present="[nonexistent]")
    )

    with pytest.raises(LabelError, match="unknown skill id in skills_present: 'nonexistent'"):
        load_labels(labels_dir, taxonomy=taxonomy)


def test_unknown_role_id_rejected(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(labels_dir, "practice", "prac_001.yaml", valid_label(roles_fit="[nonexistent]"))

    with pytest.raises(LabelError, match="unknown role id in roles_fit: 'nonexistent'"):
        load_labels(labels_dir, taxonomy=taxonomy)


def test_skill_in_present_and_ambiguous_rejected(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(
        labels_dir,
        "practice",
        "prac_001.yaml",
        valid_label(skills_present="[python]", skills_ambiguous="[python]"),
    )

    with pytest.raises(
        LabelError, match="skill 'python' appears in both skills_present and skills_ambiguous"
    ):
        load_labels(labels_dir, taxonomy=taxonomy)


def test_role_in_fit_and_should_exclude_rejected(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(
        labels_dir,
        "practice",
        "prac_001.yaml",
        valid_label(roles_fit="[ml_engineer]", roles_should_exclude="[ml_engineer]"),
    )

    with pytest.raises(
        LabelError, match="role 'ml_engineer' appears in both roles_fit and roles_should_exclude"
    ):
        load_labels(labels_dir, taxonomy=taxonomy)


def test_duplicate_resume_id_rejected(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(
        labels_dir, "practice", "prac_001.yaml", valid_label(file_name="prac_001.pdf", sha=SHA_A)
    )
    write_label(
        labels_dir,
        "practice",
        "prac_001_dup.yaml",
        valid_label(file_name="prac_001b.pdf", sha=SHA_B),
    )

    with pytest.raises(LabelError, match="duplicate resume_id 'prac_001'"):
        load_labels(labels_dir, taxonomy=taxonomy)


def test_duplicate_file_sha256_rejected(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(
        labels_dir, "practice", "prac_001.yaml", valid_label(resume_id="prac_001", sha=SHA_A)
    )
    write_label(
        labels_dir,
        "practice",
        "prac_002.yaml",
        valid_label(resume_id="prac_002", file_name="prac_002.pdf", sha=SHA_A),
    )

    with pytest.raises(LabelError, match=f"duplicate file_sha256 '{SHA_A}'"):
        load_labels(labels_dir, taxonomy=taxonomy)


def test_resume_id_prefix_set_mismatch_rejected(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(
        labels_dir, "exam", "exam_001.yaml", valid_label(resume_id="exam_001", set="practice")
    )

    with pytest.raises(LabelError, match="resume_id prefix 'exam_' does not match set 'practice'"):
        load_labels(labels_dir, taxonomy=taxonomy)


def test_taxonomy_version_mismatch_rejected(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(labels_dir, "practice", "prac_001.yaml", valid_label(taxonomy_version="9.9.9"))

    with pytest.raises(
        LabelError, match="taxonomy_version '9.9.9' does not match current taxonomy_version"
    ):
        load_labels(labels_dir, taxonomy=taxonomy)


def test_multiple_violations_reported_in_one_error(tmp_path: Path):
    taxonomy = make_taxonomy(tmp_path)
    labels_dir = tmp_path / "labels"
    write_label(
        labels_dir,
        "practice",
        "prac_001.yaml",
        valid_label(skills_present="[nonexistent]", roles_fit="[nonexistent_role]"),
    )

    with pytest.raises(LabelError) as exc_info:
        load_labels(labels_dir, taxonomy=taxonomy)
    message = str(exc_info.value)
    assert "unknown skill id in skills_present: 'nonexistent'" in message
    assert "unknown role id in roles_fit: 'nonexistent_role'" in message
