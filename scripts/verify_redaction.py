"""Verify a redacted resume directory actually contains no detectable PII.

Unlike scan_pii.py, this IS a gate: it exits 1 if any PII is found in the
redacted directory, or if the file count doesn't match the original
directory (a silently skipped or dropped file is also a failure).

Run with:
  uv run python scripts/verify_redaction.py --original-dir resumes --redacted-dir resumes_clean
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from compass.resume_intake.redact import scan_directory
from compass.resume_intake.text import SUPPORTED_EXTENSIONS


def _count_supported_files(directory: Path) -> int:
    return sum(1 for p in directory.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS)


def verify(original_dir: Path, redacted_dir: Path) -> bool:
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

    for file_name, counts in scan_directory(redacted_dir).items():
        total = sum(counts.values())
        if total:
            detail = ", ".join(f"{kind}={n}" for kind, n in sorted(counts.items()))
            print(f"error: {file_name}: PII still present ({detail})", file=sys.stderr)
            ok = False

    return ok


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-dir", type=Path, required=True)
    parser.add_argument("--redacted-dir", type=Path, required=True)
    args = parser.parse_args()

    if verify(args.original_dir, args.redacted_dir):
        print("OK — no PII detected in redacted directory.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
