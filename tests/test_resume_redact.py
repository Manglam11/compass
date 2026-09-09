"""Tests for compass.resume_intake.redact.

No real resume is used anywhere here — every fixture is built in tmp_path.
"""

from __future__ import annotations

from pathlib import Path

import docx
import pymupdf
import pytest

from compass.extract.pdf_text import extract_text as extract_pdf_text
from compass.resume_intake.redact import SameDirectoryError, redact_directory


def _make_pdf(path: Path, lines: list[str]) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((72, 72 + i * 20), line)
    doc.save(path)
    doc.close()


def _make_docx(path: Path, paragraphs: list[str]) -> None:
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    document.save(path)


def test_refuses_when_input_and_output_dirs_match(tmp_path: Path):
    with pytest.raises(SameDirectoryError):
        redact_directory(tmp_path, tmp_path, dry_run=True)


def test_dry_run_writes_nothing(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    _make_docx(input_dir / "resume.docx", ["Email me at jane.doe@example.com please."])

    results = redact_directory(input_dir, output_dir, dry_run=True)

    assert results["resume.docx"]["email"] == 1
    assert not output_dir.exists()
    assert list(input_dir.iterdir()) == [input_dir / "resume.docx"]


def test_docx_email_is_replaced(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    _make_docx(
        input_dir / "resume.docx",
        ["Experienced engineer.", "Email me at jane.doe@example.com please."],
    )

    results = redact_directory(input_dir, output_dir, dry_run=False)

    assert results["resume.docx"]["email"] == 1
    redacted_path = output_dir / "resume.docx"
    assert redacted_path.exists()

    redacted_document = docx.Document(str(redacted_path))
    full_text = "\n".join(p.text for p in redacted_document.paragraphs)
    assert "jane.doe@example.com" not in full_text
    assert "[EMAIL]" in full_text

    # the input file itself must be untouched
    original_document = docx.Document(str(input_dir / "resume.docx"))
    original_text = "\n".join(p.text for p in original_document.paragraphs)
    assert "jane.doe@example.com" in original_text


def test_pdf_redaction_removes_email_from_text_layer(tmp_path: Path):
    input_dir = tmp_path / "in"
    output_dir = tmp_path / "out"
    input_dir.mkdir()

    pdf_path = input_dir / "resume.pdf"
    _make_pdf(
        pdf_path,
        [
            "Experienced Python and SQL developer.",
            "Contact: jane.doe@example.com for details.",
            "Skilled in Docker, AWS, and PostgreSQL.",
        ],
    )

    results = redact_directory(input_dir, output_dir, dry_run=False)

    assert results["resume.pdf"]["email"] == 1
    redacted_path = output_dir / "resume.pdf"
    assert redacted_path.exists()

    redacted_text = extract_pdf_text(redacted_path)
    assert "jane.doe@example.com" not in redacted_text
    assert "[EMAIL]" in redacted_text

    # the input file itself must be untouched
    original_text = extract_pdf_text(pdf_path)
    assert "jane.doe@example.com" in original_text
