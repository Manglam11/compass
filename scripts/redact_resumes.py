"""Redact suspected PII (email/phone/linkedin/github/url) from resumes.

Writes redacted copies to --output-dir, which must differ from
--input-dir. Defaults to --dry-run, which reports counts without writing
anything. Names are not detected automatically; pass --names-file to also
redact names, one `<resume_id>: <name>` mapping per resume (see
compass.resume_intake.names) — each resume's name is redacted from that
resume only.

Run with:
  uv run python scripts/redact_resumes.py --input-dir resumes --output-dir out
  uv run python scripts/redact_resumes.py --input-dir resumes --output-dir out --no-dry-run
  uv run python scripts/redact_resumes.py --input-dir resumes --output-dir out --names-file names.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from compass.resume_intake.names import (
    NamesFileError,
    compile_name_patterns,
    load_name_map,
    unknown_resume_ids,
)
from compass.resume_intake.redact import (
    RedactionOvermatchError,
    SameDirectoryError,
    redact_directory,
)
from compass.resume_intake.text import SUPPORTED_EXTENSIONS


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    parser.add_argument("--names-file", type=Path, default=None)
    parser.set_defaults(dry_run=True)
    args = parser.parse_args()

    name_patterns = None
    if args.names_file is not None:
        try:
            mapping = load_name_map(args.names_file)
        except NamesFileError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

        known_ids = {
            p.stem for p in args.input_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS
        }
        for resume_id in unknown_resume_ids(mapping, known_ids):
            print(
                f"warning: names file has resume_id {resume_id!r} with no matching file "
                f"in {args.input_dir}",
                file=sys.stderr,
            )
        name_patterns = compile_name_patterns(mapping)

    try:
        results = redact_directory(args.input_dir, args.output_dir, args.dry_run, name_patterns)
    except (SameDirectoryError, RedactionOvermatchError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    verb = "would redact" if args.dry_run else "redacted"
    for file_name, counts in results.items():
        total = sum(counts.values())
        detail = ", ".join(f"{kind}={n}" for kind, n in sorted(counts.items())) or "none"
        print(f"{file_name}: {verb} {total} span(s) ({detail})")

    if args.dry_run:
        print("\ndry run — nothing written. Pass --no-dry-run to write redacted copies.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
