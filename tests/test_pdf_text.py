"""Tests for compass.extract.pdf_text."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from compass.extract.pdf_text import InsufficientTextError, extract_text


def test_extract_text_raises_on_text_free_pdf(tmp_path: Path):
    path = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    doc.close()

    with pytest.raises(InsufficientTextError):
        extract_text(path)


def test_extract_text_returns_page_text(tmp_path: Path):
    path = tmp_path / "resume.pdf"
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

    text = extract_text(path)
    assert len(text) >= 100
    assert "Python" in text
