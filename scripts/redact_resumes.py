"""Redact suspected PII (email/phone/linkedin/github/url) from resumes.

Writes redacted copies to --output-dir, which must differ from
--input-dir. Defaults to --dry-run, which reports counts without writing
anything. Name redaction is out of scope and must be done manually.

Run with:
  uv run python scripts/redact_resumes.py --input-dir resumes --output-dir out
  uv run python scripts/redact_resumes.py --input-dir resumes --output-dir out --no-dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from compass.resume_intake.redact import SameDirectoryError, redact_directory


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    parser.set_defaults(dry_run=True)
    args = parser.parse_args()

    try:
        results = redact_directory(args.input_dir, args.output_dir, args.dry_run)
    except SameDirectoryError as exc:
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
