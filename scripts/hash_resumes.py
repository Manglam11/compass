"""Emit resume_id, file_name, sha256 for every resume in a directory.

Reads only file bytes for hashing — never extracts or prints resume text.

Run with: uv run python scripts/hash_resumes.py <resumes_dir>
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from compass.resume_intake.hashing import hash_resumes


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()

    writer = csv.writer(sys.stdout)
    writer.writerow(["resume_id", "file_name", "sha256"])
    for resume_id, file_name, sha256 in hash_resumes(args.directory):
        writer.writerow([resume_id, file_name, sha256])

    return 0


if __name__ == "__main__":
    sys.exit(main())
