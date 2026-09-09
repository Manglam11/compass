"""Generate empty label stubs for redacted resumes.

See compass.labels.stubs for what a stub contains and why. Refuses to
overwrite any existing label file: if any target already exists, nothing
is written and the run exits 1.

Run with: uv run python scripts/make_label_stubs.py <resumes_clean_dir> <labels_practice_dir>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from compass.labels.stubs import make_label_stubs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resumes_dir", type=Path)
    parser.add_argument("labels_dir", type=Path)
    args = parser.parse_args()

    try:
        written = make_label_stubs(args.resumes_dir, args.labels_dir)
    except FileExistsError as exc:
        (existing,) = exc.args
        for path in existing:
            print(f"refusing to overwrite existing label file: {path}")
        return 1

    print(f"{len(written)} label stub(s) written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
