"""Redact suspected PII from resumes into a separate output directory.

PDF redaction uses PyMuPDF's true redaction (add_redact_annot +
apply_redactions), which strips the underlying content — not a drawn box,
which would leave the original text extractable underneath.

DOCX redaction rewrites the runs that make up each paragraph (and table
cell) in place. Name redaction is out of scope; only email/phone/linkedin/
github/url spans are touched.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import docx
import pymupdf

from compass.resume_intake.pii import PLACEHOLDER, PIIMatch, find_pii
from compass.resume_intake.text import SUPPORTED_EXTENSIONS


class SameDirectoryError(Exception):
    pass


def _scan_pdf_counts(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    doc = pymupdf.open(path)
    try:
        for page in doc:
            for match in find_pii(page.get_text()):
                counts[match.kind] += 1
    finally:
        doc.close()
    return counts


def _redact_pdf(input_path: Path, output_path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    doc = pymupdf.open(input_path)
    try:
        for page in doc:
            for match in find_pii(page.get_text()):
                rects = page.search_for(match.value)
                if not rects:
                    continue
                placeholder = PLACEHOLDER[match.kind]
                for rect in rects:
                    page.add_redact_annot(rect, text=placeholder, fill=(0, 0, 0))
                counts[match.kind] += 1
            page.apply_redactions()
        doc.save(output_path)
    finally:
        doc.close()
    return counts


def _paragraph_texts(document: docx.document.Document) -> list:
    paragraphs = list(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                paragraphs.extend(cell.paragraphs)
    return paragraphs


def _scan_docx_counts(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    document = docx.Document(str(path))
    for paragraph in _paragraph_texts(document):
        for match in find_pii(paragraph.text):
            counts[match.kind] += 1
    return counts


def _run_containing(match: PIIMatch, offsets: list[tuple[int, int]]) -> int | None:
    for i, (start, end) in enumerate(offsets):
        if start <= match.start and match.end <= end:
            return i
    return None


def _redact_paragraph(paragraph, counts: Counter[str]) -> None:
    runs = paragraph.runs
    if not runs:
        return

    texts = [run.text for run in runs]
    full_text = "".join(texts)
    matches = find_pii(full_text)
    if not matches:
        return

    offsets: list[tuple[int, int]] = []
    pos = 0
    for t in texts:
        offsets.append((pos, pos + len(t)))
        pos += len(t)

    run_of_match = {id(m): _run_containing(m, offsets) for m in matches}

    if all(idx is not None for idx in run_of_match.values()):
        for i, run in enumerate(runs):
            run_start, _ = offsets[i]
            run_matches = [m for m in matches if run_of_match[id(m)] == i]
            if not run_matches:
                continue
            text = run.text
            for match in sorted(run_matches, key=lambda m: -m.start):
                local_start = match.start - run_start
                local_end = match.end - run_start
                text = text[:local_start] + PLACEHOLDER[match.kind] + text[local_end:]
                counts[match.kind] += 1
            run.text = text
    else:
        # A match spans a run boundary — rebuild the whole paragraph into
        # the first run rather than trying to split it across runs.
        new_text = full_text
        for match in sorted(matches, key=lambda m: -m.start):
            new_text = new_text[: match.start] + PLACEHOLDER[match.kind] + new_text[match.end :]
            counts[match.kind] += 1
        runs[0].text = new_text
        for run in runs[1:]:
            run.text = ""


def _redact_docx(input_path: Path, output_path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    document = docx.Document(str(input_path))
    for paragraph in _paragraph_texts(document):
        _redact_paragraph(paragraph, counts)
    document.save(output_path)
    return counts


def redact_directory(input_dir: Path, output_dir: Path, dry_run: bool) -> dict[str, Counter[str]]:
    if input_dir.resolve() == output_dir.resolve():
        raise SameDirectoryError("--output-dir must be different from --input-dir")

    paths = sorted(p for p in input_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)
    results: dict[str, Counter[str]] = {}

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    for path in paths:
        is_pdf = path.suffix.lower() == ".pdf"
        if dry_run:
            results[path.name] = _scan_pdf_counts(path) if is_pdf else _scan_docx_counts(path)
        else:
            output_path = output_dir / path.name
            results[path.name] = (
                _redact_pdf(path, output_path) if is_pdf else _redact_docx(path, output_path)
            )

    return results
