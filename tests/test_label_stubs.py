"""Tests for compass.labels.stubs.

Uses the real repo taxonomy (via compass.labels.loader.DEFAULT_*_PATH) since
make_label_stubs reads taxonomy_version from it — no sample resumes are
committed, so resume fixtures are built in tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from compass.labels.loader import DEFAULT_ROLES_PATH, LabelError, load_labels
from compass.labels.stubs import make_label_stubs
from compass.resume_intake.hashing import sha256_of
from compass.taxonomy.loader import load_taxonomy


def real_taxonomy():
    from compass.labels.loader import DEFAULT_SKILLS_PATH

    return load_taxonomy(DEFAULT_SKILLS_PATH, DEFAULT_ROLES_PATH)


def test_make_label_stubs_writes_one_per_resume(tmp_path: Path):
    resumes_dir = tmp_path / "resumes_clean"
    resumes_dir.mkdir()
    (resumes_dir / "prac_001.pdf").write_bytes(b"hello")
    (resumes_dir / "prac_002.docx").write_bytes(b"world")
    labels_dir = tmp_path / "labels" / "practice"

    written = make_label_stubs(resumes_dir, labels_dir)

    assert sorted(p.name for p in written) == ["prac_001.yaml", "prac_002.yaml"]


def test_stub_fields_match_actual_file(tmp_path: Path):
    resumes_dir = tmp_path / "resumes_clean"
    resumes_dir.mkdir()
    resume_path = resumes_dir / "prac_001.pdf"
    resume_path.write_bytes(b"hello")
    labels_dir = tmp_path / "labels" / "practice"

    make_label_stubs(resumes_dir, labels_dir)

    stub = yaml.safe_load((labels_dir / "prac_001.yaml").read_text(encoding="utf-8"))
    taxonomy = real_taxonomy()

    assert stub["resume_id"] == "prac_001"
    assert stub["file_sha256"] == sha256_of(resume_path)
    assert stub["taxonomy_version"] == taxonomy.taxonomy_version
    assert stub["format"] == "pdf"
    assert stub["status"] == "draft"
    assert stub["skills_present"] == []
    assert stub["skills_ambiguous"] == []
    assert stub["roles_fit"] == []
    assert stub["roles_should_exclude"] == []


def test_stub_passes_loader_structural_validation(tmp_path: Path):
    resumes_dir = tmp_path / "resumes_clean"
    resumes_dir.mkdir()
    (resumes_dir / "prac_001.pdf").write_bytes(b"hello")
    labels_dir = tmp_path / "labels" / "practice"

    make_label_stubs(resumes_dir, labels_dir)

    taxonomy = real_taxonomy()
    labels = load_labels(labels_dir, taxonomy=taxonomy)

    assert len(labels) == 1
    assert labels[0].resume_id == "prac_001"
    assert labels[0].status == "draft"


def test_stub_rejected_by_require_final(tmp_path: Path):
    resumes_dir = tmp_path / "resumes_clean"
    resumes_dir.mkdir()
    (resumes_dir / "prac_001.pdf").write_bytes(b"hello")
    labels_dir = tmp_path / "labels" / "practice"

    make_label_stubs(resumes_dir, labels_dir)

    taxonomy = real_taxonomy()

    with pytest.raises(LabelError, match="final labels required"):
        load_labels(labels_dir, taxonomy=taxonomy, require_final=True)


def test_refuses_to_overwrite_existing_label(tmp_path: Path):
    resumes_dir = tmp_path / "resumes_clean"
    resumes_dir.mkdir()
    (resumes_dir / "prac_001.pdf").write_bytes(b"hello")
    labels_dir = tmp_path / "labels" / "practice"

    make_label_stubs(resumes_dir, labels_dir)
    original = (labels_dir / "prac_001.yaml").read_text(encoding="utf-8")

    with pytest.raises(FileExistsError):
        make_label_stubs(resumes_dir, labels_dir)

    assert (labels_dir / "prac_001.yaml").read_text(encoding="utf-8") == original


def test_refuses_whole_batch_if_any_target_exists(tmp_path: Path):
    resumes_dir = tmp_path / "resumes_clean"
    resumes_dir.mkdir()
    (resumes_dir / "prac_001.pdf").write_bytes(b"hello")
    labels_dir = tmp_path / "labels" / "practice"
    labels_dir.mkdir(parents=True)
    (labels_dir / "prac_001.yaml").write_text("hand-labelled: true\n", encoding="utf-8")
    (resumes_dir / "prac_002.pdf").write_bytes(b"world")

    with pytest.raises(FileExistsError):
        make_label_stubs(resumes_dir, labels_dir)

    assert not (labels_dir / "prac_002.yaml").exists()
    assert (labels_dir / "prac_001.yaml").read_text(encoding="utf-8") == "hand-labelled: true\n"
