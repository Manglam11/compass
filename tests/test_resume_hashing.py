"""Tests for compass.resume_intake.hashing."""

from __future__ import annotations

from pathlib import Path

from compass.resume_intake.hashing import hash_resumes


def test_hash_resumes_known_bytes(tmp_path: Path):
    (tmp_path / "b.pdf").write_bytes(b"hello world")
    (tmp_path / "a.docx").write_bytes(b"")

    rows = hash_resumes(tmp_path)

    assert rows == [
        ("a", "a.docx", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        ("b", "b.pdf", "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"),
    ]


def test_hash_resumes_ignores_non_resume_files(tmp_path: Path):
    (tmp_path / "notes.txt").write_bytes(b"not a resume")
    (tmp_path / "one.pdf").write_bytes(b"hello world")

    rows = hash_resumes(tmp_path)

    assert [row[1] for row in rows] == ["one.pdf"]


def test_hash_resumes_sorted_by_resume_id(tmp_path: Path):
    (tmp_path / "z.pdf").write_bytes(b"z")
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "m.docx").write_bytes(b"m")

    rows = hash_resumes(tmp_path)

    assert [row[0] for row in rows] == ["a", "m", "z"]
