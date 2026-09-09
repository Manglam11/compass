"""Tests for compass.pipeline."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from compass.extract.pdf_text import InsufficientTextError
from compass.pipeline import analyse_resume


def _write_resume_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    lines = [
        "Experienced Python and SQL developer.",
        "Built data pipelines and dashboards for five years.",
        "Skilled in Docker, AWS, and PostgreSQL.",
    ]
    for i, line in enumerate(lines):
        page.insert_text((72, 72 + i * 20), line)
    doc.save(path)
    doc.close()


def test_analyse_resume_returns_populated_result(tmp_path: Path):
    path = tmp_path / "resume.pdf"
    _write_resume_pdf(path)

    result = analyse_resume(path)

    assert result.character_count > 0
    assert "python" in result.found_skills
    assert "sql" in result.found_skills
    assert "docker" in result.found_skills
    assert "aws" in result.found_skills
    assert "postgresql" in result.found_skills


def test_analyse_resume_is_deterministic(tmp_path: Path):
    path = tmp_path / "resume.pdf"
    _write_resume_pdf(path)

    first = analyse_resume(path)
    second = analyse_resume(path)

    assert first == second


def test_analyse_resume_raises_on_text_free_pdf(tmp_path: Path):
    path = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()

    with pytest.raises(InsufficientTextError):
        analyse_resume(path)
