"""Strip every image from resume PDFs and DOCX files. Never touches the text layer.

The audit (scripts/audit_images.py) found the text-layer PII pipeline is
blind to images: headshots, scanned certificates, and off-page decorative
images all pass through undetected. This removes every image from every
PDF page — no size threshold, no area-fraction guard — using
page.apply_redactions() with images=PDF_REDACT_IMAGE_REMOVE and
text=PDF_REDACT_TEXT_NONE, so the extracted text is left byte-for-byte
identical.

DOCX images are removed by rewriting the zip archive without any
word/media/ entry, and without the corresponding <Relationship> entries in
the *.rels parts (any relationship whose Target starts with "media/") so
the package has no dangling relationship pointing at a removed part. The
inline references to those relationship ids that remain in document.xml
(or headers/footers/numbering.xml) are left as-is — python-docx's text
extraction never dereferences them, so the file still opens and its text
is unaffected; this is exercised directly by the round-trip-open test in
tests/test_strip_images.py.

A file that has zero text characters after stripping, but had at least one
image in the input, is flagged blank_after_strip — it must not be silently
scored as a 0-skill candidate downstream.

Run with:
  uv run python scripts/strip_images.py --in-dir resumes_clean --out-dir resumes_stripped
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pymupdf

from compass.resume_intake.text import extract_resume_text, iter_resume_files

_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
ET.register_namespace("", _RELS_NS)


def strip_pdf_images(in_path: Path, out_path: Path) -> tuple[int, int, int]:
    """Return (images_before, images_after, text_chars_after)."""
    with pymupdf.open(in_path) as doc:
        images_before = sum(len(page.get_images(full=True)) for page in doc)
        for page in doc:
            page.add_redact_annot(page.rect)
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_REMOVE,
                text=pymupdf.PDF_REDACT_TEXT_NONE,
            )
        doc.save(out_path, garbage=4, deflate=True)

    with pymupdf.open(out_path) as doc:
        images_after = sum(len(page.get_images(full=True)) for page in doc)
        text_chars = sum(len(page.get_text()) for page in doc)

    return images_before, images_after, text_chars


def _strip_media_relationships(data: bytes) -> bytes:
    root = ET.fromstring(data)
    for rel in list(root):
        if rel.get("Target", "").startswith("media/"):
            root.remove(rel)
    return ET.tostring(root, xml_declaration=True, encoding="UTF-8")


def strip_docx_images(in_path: Path, out_path: Path) -> tuple[int, int, int]:
    """Return (media_before, media_after, text_chars_after)."""
    with zipfile.ZipFile(in_path) as archive:
        infos = archive.infolist()
        data_by_name = {info.filename: archive.read(info.filename) for info in infos}

    media_before = sum(1 for info in infos if info.filename.startswith("word/media/"))

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for info in infos:
            if info.filename.startswith("word/media/"):
                continue
            data = data_by_name[info.filename]
            if info.filename.endswith(".rels"):
                data = _strip_media_relationships(data)
            archive.writestr(info, data)

    with zipfile.ZipFile(out_path) as archive:
        media_after = sum(1 for name in archive.namelist() if name.startswith("word/media/"))
    text_chars = len(extract_resume_text(out_path))

    return media_before, media_after, text_chars


def strip_directory(in_dir: Path, out_dir: Path) -> int:
    files_processed = 0
    total_removed = 0
    blank_count = 0
    any_failure = False

    out_dir.mkdir(parents=True, exist_ok=True)

    for path in iter_resume_files(in_dir):
        out_path = out_dir / path.name

        if path.suffix.lower() == ".docx":
            images_before, images_after, text_chars = strip_docx_images(path, out_path)
        else:
            images_before, images_after, text_chars = strip_pdf_images(path, out_path)

        removed = images_before - images_after
        total_removed += removed
        print(f"{path.name}: removed={removed} remaining={images_after} text_chars={text_chars}")

        if images_after > 0:
            print(
                f"FAILURE: {path.name} still has {images_after} image(s) after stripping",
                file=sys.stderr,
            )
            any_failure = True

        if text_chars == 0 and images_before > 0:
            print(f"blank_after_strip: {path.name}")
            blank_count += 1

        files_processed += 1

    exit_code = 1 if any_failure else 0
    print("=== SUMMARY ===")
    print(f"files processed: {files_processed}")
    print(f"total images removed: {total_removed}")
    print(f"blank_after_strip count: {blank_count}")
    print(f"exit code: {exit_code}")

    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-dir", type=Path, required=True, dest="in_dir")
    parser.add_argument("--out-dir", type=Path, required=True, dest="out_dir")
    args = parser.parse_args()

    if args.in_dir.resolve() == args.out_dir.resolve():
        print("error: --in-dir and --out-dir resolve to the same directory", file=sys.stderr)
        return 1

    return strip_directory(args.in_dir, args.out_dir)


if __name__ == "__main__":
    sys.exit(main())
