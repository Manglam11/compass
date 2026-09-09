"""Format-dispatching resume text extraction (pdf, docx)."""

from __future__ import annotations

from pathlib import Path

from compass.extract.docx_text import extract_text as _extract_docx_text
from compass.extract.pdf_text import extract_text as _extract_pdf_text

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


def extract_resume_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix == ".docx":
        return _extract_docx_text(path)
    raise ValueError(f"unsupported resume format: {suffix}")


def iter_resume_files(directory: Path):
    return sorted(p for p in directory.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)
