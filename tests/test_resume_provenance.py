"""Tests for compass.resume_intake.provenance."""

from __future__ import annotations

from pathlib import Path

from compass.resume_intake.provenance import build_provenance_rows


def test_build_provenance_rows_source_always_unknown(tmp_path: Path):
    (tmp_path / "b.pdf").write_bytes(b"hello")
    (tmp_path / "a.docx").write_bytes(b"world")

    rows = build_provenance_rows(tmp_path)

    assert [row[1] for row in rows] == ["unknown", "unknown"]


def test_build_provenance_rows_format_from_extension(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"hello")
    (tmp_path / "b.docx").write_bytes(b"world")

    rows = build_provenance_rows(tmp_path)

    assert [row[0] for row in rows] == ["a", "b"]
    assert [row[3] for row in rows] == ["pdf", "docx"]


def test_build_provenance_rows_ignores_non_resume_files(tmp_path: Path):
    (tmp_path / "notes.txt").write_bytes(b"not a resume")
    (tmp_path / "one.pdf").write_bytes(b"hello")

    rows = build_provenance_rows(tmp_path)

    assert [row[0] for row in rows] == ["one"]


def test_build_provenance_rows_sorted_by_resume_id(tmp_path: Path):
    (tmp_path / "z.pdf").write_bytes(b"z")
    (tmp_path / "a.pdf").write_bytes(b"a")
    (tmp_path / "m.docx").write_bytes(b"m")

    rows = build_provenance_rows(tmp_path)

    assert [row[0] for row in rows] == ["a", "m", "z"]


def test_build_provenance_rows_other_columns_blank(tmp_path: Path):
    (tmp_path / "a.pdf").write_bytes(b"a")

    rows = build_provenance_rows(tmp_path)

    assert rows == [["a", "unknown", "", "pdf", "", "", ""]]
