"""Tests for scripts/strip_images.py.

All fixtures are built in-memory with PyMuPDF — never read from resumes/ or
resumes_clean/.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from strip_images import main, strip_directory, strip_pdf_images


def _red_png() -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 10, 10), False)
    pix.set_rect(pix.irect, (255, 0, 0))
    return pix.tobytes("png")


def _make_pdf(path: Path, *, with_image: bool, with_text: bool) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    if with_image:
        page.insert_image(pymupdf.Rect(10, 10, 60, 60), stream=_red_png())
    if with_text:
        page.insert_text((100, 100), "Experienced Python and SQL developer.")
    doc.save(path)
    doc.close()


def test_strips_image_preserves_text(tmp_path: Path):
    in_path = tmp_path / "in.pdf"
    out_path = tmp_path / "out.pdf"
    _make_pdf(in_path, with_image=True, with_text=True)

    images_before, images_after, text_chars = strip_pdf_images(in_path, out_path)

    assert images_before == 1
    assert images_after == 0
    assert text_chars > 0

    with pymupdf.open(out_path) as doc:
        assert sum(len(page.get_images(full=True)) for page in doc) == 0
        assert "Python" in "".join(page.get_text() for page in doc)


def test_blank_after_strip_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    _make_pdf(in_dir / "photo_only.pdf", with_image=True, with_text=False)

    exit_code = strip_directory(in_dir, out_dir)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "blank_after_strip: photo_only.pdf" in captured.out


def test_no_images_passes_through(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    _make_pdf(in_dir / "text_only.pdf", with_image=False, with_text=True)

    exit_code = strip_directory(in_dir, out_dir)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "blank_after_strip: text_only.pdf" not in captured.out
    assert "removed=0 remaining=0" in captured.out


def test_in_dir_equal_to_out_dir_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    in_dir = tmp_path / "same"
    in_dir.mkdir()
    _make_pdf(in_dir / "resume.pdf", with_image=True, with_text=True)

    monkeypatch.setattr(
        sys, "argv", ["strip_images.py", "--in-dir", str(in_dir), "--out-dir", str(in_dir)]
    )

    exit_code = main()

    assert exit_code != 0
    with pymupdf.open(in_dir / "resume.pdf") as doc:
        assert sum(len(page.get_images(full=True)) for page in doc) == 1
