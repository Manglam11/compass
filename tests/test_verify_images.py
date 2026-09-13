"""Tests for the image check added to scripts/verify_redaction.py.

All fixtures are built in-memory with PyMuPDF — never read from resumes/,
resumes_clean/, or resumes_stripped/.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from verify_redaction import check_images, verify


def _red_png() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), False)
    pix.set_rect(pix.irect, (255, 0, 0))
    return pix.tobytes("png")


def _make_pdf(path: Path, *, with_image: bool, with_text: bool = True) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    if with_image:
        page.insert_image(pymupdf.Rect(10, 10, 60, 60), stream=_red_png())
    if with_text:
        page.insert_text((100, 100), "Experienced Python and SQL developer.")
    doc.save(path)
    doc.close()


def _make_docx_with_media(path: Path, media_count: int) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "word/document.xml",
            "<w:document><w:body><w:p><w:r><w:t>Resume text.</w:t>"
            "</w:r></w:p></w:body></w:document>",
        )
        for i in range(media_count):
            archive.writestr(f"word/media/image{i + 1}.png", _red_png())


def test_clean_pdf_directory_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _make_pdf(tmp_path / "clean.pdf", with_image=False)

    ok = check_images(tmp_path)
    captured = capsys.readouterr()

    assert ok
    assert captured.err == ""


def test_pdf_with_image_fails_and_names_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _make_pdf(tmp_path / "headshot.pdf", with_image=True)

    ok = check_images(tmp_path)
    captured = capsys.readouterr()

    assert not ok
    assert "headshot.pdf" in captured.err
    assert "1 image" in captured.err


def test_docx_with_images_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    _make_pdf(tmp_path / "clean.pdf", with_image=False)
    _make_docx_with_media(tmp_path / "prac.docx", 3)

    ok = check_images(tmp_path)
    captured = capsys.readouterr()

    assert not ok
    assert "prac.docx" in captured.err
    assert "3 image" in captured.err


def test_verify_reports_text_pii_and_pdf_image_together(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    original_dir = tmp_path / "original"
    redacted_dir = tmp_path / "redacted"
    original_dir.mkdir()
    redacted_dir.mkdir()

    _make_pdf(original_dir / "a.pdf", with_image=False)
    _make_pdf(redacted_dir / "a.pdf", with_image=True)

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Contact me at leaked@example.com for details.")
    doc.save(redacted_dir / "b.pdf")
    doc.close()
    doc = pymupdf.open()
    doc.new_page()
    doc.save(original_dir / "b.pdf")
    doc.close()

    ok = verify(original_dir, redacted_dir)
    captured = capsys.readouterr()

    assert not ok
    assert "a.pdf" in captured.err
    assert "image" in captured.err
    assert "b.pdf" in captured.err
    assert "PII still present" in captured.err
