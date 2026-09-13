"""Verify a redacted resume directory actually contains no detectable PII.

Unlike scan_pii.py, this IS a gate: it exits 1 if any PII is found in the
redacted directory, or if the file count doesn't match the original
directory (a silently skipped or dropped file is also a failure). Pass
--names-file to also gate on names — a `<resume_id>: <name>` mapping, one
per resume (see compass.resume_intake.names); without it, names are not
checked. Each resume is checked against its own name only, never anyone
else's.

Run with:
  uv run python scripts/verify_redaction.py --original-dir resumes --redacted-dir resumes_clean
  uv run python scripts/verify_redaction.py --original-dir resumes --redacted-dir resumes_clean --names-file names.txt
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

import pymupdf

from compass.resume_intake.names import (
    NamesFileError,
    compile_name_patterns,
    load_name_map,
    unknown_resume_ids,
)
from compass.resume_intake.redact import scan_directory
from compass.resume_intake.text import SUPPORTED_EXTENSIONS, iter_resume_files


def _count_supported_files(directory: Path) -> int:
    return sum(1 for p in directory.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)


def check_images(redacted_dir: Path) -> bool:
    """Report per-file image counts and fail on any surviving image.

    A PDF or DOCX with any image fails the run. Only filenames and counts
    are printed — never text.
    """
    ok = True

    for path in iter_resume_files(redacted_dir):
        if path.suffix.lower() == ".pdf":
            with pymupdf.open(path) as doc:
                count = sum(len(page.get_images(full=True)) for page in doc)
            if count > 0:
                print(f"error: {path.name}: {count} image(s) still present in PDF", file=sys.stderr)
                ok = False
        else:
            with zipfile.ZipFile(path) as archive:
                count = sum(
                    1 for info in archive.infolist() if info.filename.startswith("word/media/")
                )
            if count > 0:
                print(
                    f"error: {path.name}: {count} image(s) still present in docx media",
                    file=sys.stderr,
                )
                ok = False

    return ok


def verify(
    original_dir: Path,
    redacted_dir: Path,
    name_patterns: dict[str, re.Pattern[str]] | None = None,
) -> bool:
    ok = True

    original_count = _count_supported_files(original_dir)
    redacted_count = _count_supported_files(redacted_dir)
    if original_count != redacted_count:
        print(
            f"error: file count mismatch — {original_count} in {original_dir}, "
            f"{redacted_count} in {redacted_dir}",
            file=sys.stderr,
        )
        ok = False

    for file_name, counts in scan_directory(redacted_dir, name_patterns).items():
        total = sum(counts.values())
        if total:
            detail = ", ".join(f"{kind}={n}" for kind, n in sorted(counts.items()))
            print(f"error: {file_name}: PII still present ({detail})", file=sys.stderr)
            ok = False

    if not check_images(redacted_dir):
        ok = False

    return ok


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-dir", type=Path, required=True)
    parser.add_argument("--redacted-dir", type=Path, required=True)
    parser.add_argument("--names-file", type=Path, default=None)
    args = parser.parse_args()

    name_patterns = None
    if args.names_file is not None:
        try:
            mapping = load_name_map(args.names_file)
        except NamesFileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        known_ids = {
            p.stem for p in args.redacted_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS
        }
        for resume_id in unknown_resume_ids(mapping, known_ids):
            print(
                f"warning: names file has resume_id {resume_id!r} with no matching file "
                f"in {args.redacted_dir}",
                file=sys.stderr,
            )
        name_patterns = compile_name_patterns(mapping)

    if verify(args.original_dir, args.redacted_dir, name_patterns):
        print("OK — no PII detected in redacted directory.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
