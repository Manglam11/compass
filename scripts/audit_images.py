"""Report what image content each resume file carries. Read-only, measure-only.

Neither scan_pii.py nor verify_redaction.py can see pixels — they work over
the extracted text layer, so a photograph or an image of text is invisible to
them. This script does not fix that. It only reports, per file, what image
content exists, so a fix can be scoped. It never extracts, prints, or infers
any text from a resume: only the file stem and image geometry.

Run with:
  uv run python scripts/audit_images.py --dir resumes_clean
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import pymupdf

from compass.resume_intake.text import iter_resume_files

AREA_FRACTION_THRESHOLD = 0.90


def audit_pdf(path: Path) -> tuple[list[str], int, int]:
    lines: list[str] = []
    image_count = 0
    large_count = 0

    with pymupdf.open(path) as doc:
        lines.append(f"  pages: {doc.page_count}")
        for page_index, page in enumerate(doc, start=1):
            page_area = page.rect.get_area()
            images = page.get_images(full=True)
            if not images:
                continue
            for img in images:
                xref, width, height = img[0], img[2], img[3]
                rects = page.get_image_rects(xref)
                if not rects:
                    lines.append(
                        f"  page {page_index}: xref={xref} size={width}x{height}px "
                        f"rect=none area_frac=none"
                    )
                    continue
                for rect in rects:
                    image_count += 1
                    area_frac = rect.get_area() / page_area if page_area else 0.0
                    if area_frac >= AREA_FRACTION_THRESHOLD:
                        large_count += 1
                    rect_str = f"({rect.x0:.2f}, {rect.y0:.2f}, {rect.x1:.2f}, {rect.y1:.2f})"
                    lines.append(
                        f"  page {page_index}: xref={xref} size={width}x{height}px "
                        f"rect={rect_str} area_frac={area_frac:.3f}"
                    )

    return lines, image_count, large_count


def audit_docx(path: Path) -> tuple[list[str], int]:
    lines: list[str] = []
    media: list[tuple[str, int]] = []

    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.filename.startswith("word/media/"):
                media.append((info.filename, info.file_size))

    lines.append(f"  media entries: {len(media)}")
    for name, size in media:
        lines.append(f"  {name} {size} bytes")

    return lines, len(media)


def audit_directory(directory: Path) -> str:
    lines: list[str] = []
    ext_counts: dict[str, int] = {}
    files_with_images = 0
    total_images = 0
    total_large = 0

    for path in iter_resume_files(directory):
        suffix = path.suffix.lower()
        ext_counts[suffix] = ext_counts.get(suffix, 0) + 1

        lines.append(f"=== {path.stem}{suffix} ===")
        if suffix == ".pdf":
            file_lines, image_count, large_count = audit_pdf(path)
        else:
            file_lines, image_count = audit_docx(path)
            large_count = 0

        lines.extend(file_lines)
        lines.append("")

        if image_count > 0:
            files_with_images += 1
        total_images += image_count
        total_large += large_count

    total_files = sum(ext_counts.values())
    ext_summary = ", ".join(f"{ext}: {count}" for ext, count in sorted(ext_counts.items()))

    lines.append("=== SUMMARY ===")
    lines.append(f"files scanned: {total_files} ({ext_summary})")
    lines.append(f"files with at least one image: {files_with_images}")
    lines.append(f"total image count: {total_images}")
    lines.append(f"images with area fraction >= {AREA_FRACTION_THRESHOLD:.2f}: {total_large}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True, dest="directory")
    args = parser.parse_args()

    print(audit_directory(args.directory))
    return 0


if __name__ == "__main__":
    sys.exit(main())
