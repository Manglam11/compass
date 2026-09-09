"""Regenerate resumes/PROVENANCE.csv from the resume files actually on disk.

Source URLs were never recorded at collection time and are unrecoverable, so
source_url is always written as "unknown" — never guessed.

Run with: uv run python scripts/make_provenance.py <resumes_dir> <provenance_csv>
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from compass.resume_intake.provenance import PROVENANCE_HEADER, build_provenance_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resumes_dir", type=Path)
    parser.add_argument("provenance_csv", type=Path)
    args = parser.parse_args()

    rows = build_provenance_rows(args.resumes_dir)

    with args.provenance_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(PROVENANCE_HEADER)
        writer.writerows(rows)

    print(f"{len(rows)} row(s) written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
