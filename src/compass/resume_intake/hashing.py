"""Content-hash resume files without reading their contents as text.

Used to build a provenance record (resume_id -> sha256) without ever
loading extracted text or personal data into this repo.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

RESUME_EXTENSIONS = {".pdf", ".docx"}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_resumes(directory: Path) -> list[tuple[str, str, str]]:
    """Return (resume_id, file_name, sha256) rows, sorted by resume_id."""
    rows = [
        (path.stem, path.name, sha256_of(path))
        for path in directory.iterdir()
        if path.suffix.lower() in RESUME_EXTENSIONS
    ]
    rows.sort(key=lambda row: row[0])
    return rows
