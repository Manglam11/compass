"""Verify SHA-256 hashes of resume files referenced by labels.

Recomputes the SHA-256 of each file referenced by a resume label and reports
any mismatch against the recorded file_sha256, plus any referenced file that
is missing from the resumes directory.

Kept separate from load_labels(): the resumes directory (real resume files)
will not exist on every machine, so this check must not be part of
schema/taxonomy validation.

Run with: uv run python scripts/verify_label_hashes.py <labels_dir> <resumes_dir>
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from compass.labels.schema import ResumeLabel


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(labels_dir: Path, resumes_dir: Path) -> list[str]:
    problems: list[str] = []

    for label_path in sorted(labels_dir.rglob("*.yaml")):
        with label_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        try:
            label = ResumeLabel.model_validate(data)
        except ValidationError as exc:
            problems.append(f"{label_path.name}: could not parse label: {exc}")
            continue

        resume_path = resumes_dir / label.file_name
        if not resume_path.exists():
            problems.append(f"{label_path.name}: referenced file missing: {label.file_name}")
            continue

        actual_sha256 = _sha256_of(resume_path)
        if actual_sha256 != label.file_sha256:
            problems.append(
                f"{label_path.name}: sha256 mismatch for {label.file_name}: "
                f"expected {label.file_sha256}, got {actual_sha256}"
            )

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("labels_dir", type=Path)
    parser.add_argument("resumes_dir", type=Path)
    args = parser.parse_args()

    problems = verify(args.labels_dir, args.resumes_dir)

    if problems:
        for problem in problems:
            print(problem)
        print(f"{len(problems)} problem(s) found")
        return 1

    print("all referenced resume file hashes verified OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
