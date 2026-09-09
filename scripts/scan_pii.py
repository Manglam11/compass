"""Report suspected PII in resumes without modifying anything.

This is a report, not a gate: it always exits 0. Names are not
auto-detected unless --names-file is passed — a `<resume_id>: <name>`
mapping, one per resume (see compass.resume_intake.names) — without it,
the first 200 characters of each document are printed under a HEADER
label for manual inspection instead. Each resume's name is matched
against that resume only.

Run with:
  uv run python scripts/scan_pii.py <resumes_dir>
  uv run python scripts/scan_pii.py <resumes_dir> --names-file names.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from compass.extract.pdf_text import InsufficientTextError
from compass.resume_intake.names import (
    NamesFileError,
    compile_name_patterns,
    load_name_map,
    unknown_resume_ids,
)
from compass.resume_intake.pii import find_pii
from compass.resume_intake.text import extract_resume_text, iter_resume_files

HEADER_CHARS = 200


def scan_directory(directory: Path, name_patterns: dict[str, re.Pattern[str]] | None = None) -> str:
    lines: list[str] = []

    for path in iter_resume_files(directory):
        lines.append(f"=== {path.name} ===")
        try:
            text = extract_resume_text(path)
        except InsufficientTextError as exc:
            lines.append(f"  [skipped] {exc}")
            lines.append("")
            continue

        header = text[:HEADER_CHARS].replace("\n", " ")
        lines.append(f"  HEADER — inspect manually for name: {header!r}")

        name_pattern = name_patterns.get(path.stem) if name_patterns else None
        matches = find_pii(text, name_pattern)
        if not matches:
            lines.append("  no PII patterns detected")
        for match in matches:
            lines.append(f"  {match.kind:9s} offset={match.start:<6d} value={match.value!r}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    # Resume text can contain characters the terminal's codepage can't render
    # (bullets, curly quotes, etc.); this is a report, not a gate, so never
    # let an encoding mismatch turn into a crash.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--names-file", type=Path, default=None)
    args = parser.parse_args()

    name_patterns = None
    if args.names_file is not None:
        try:
            mapping = load_name_map(args.names_file)
        except NamesFileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        known_ids = {p.stem for p in iter_resume_files(args.directory)}
        for resume_id in unknown_resume_ids(mapping, known_ids):
            print(
                f"warning: names file has resume_id {resume_id!r} with no matching file "
                f"in {args.directory}",
                file=sys.stderr,
            )
        name_patterns = compile_name_patterns(mapping)

    print(scan_directory(args.directory, name_patterns))
    return 0


if __name__ == "__main__":
    sys.exit(main())
