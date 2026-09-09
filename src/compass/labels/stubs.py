"""Generate empty label stubs for redacted resumes.

A stub is pre-filled with resume identity (resume_id, file_sha256,
taxonomy_version) and empty judgement containers, written with
status: draft — which the label schema (see compass.labels.schema)
exempts from the skills_present/roles_fit non-empty requirement. A
labeller fills in real judgements and flips status to final before the
label counts for evaluation (compass.labels.loader.load_labels with
require_final=True).

The remaining required fields (source, layout, labeller) have no neutral
placeholder in the schema; they are written as obvious placeholders
("self", "other", "") that a labeller must overwrite before finalizing.
Unlike skills_present/roles_fit, the schema does not block finalization on
these — only a human labelling pass catches them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from compass.labels.loader import DEFAULT_ROLES_PATH, DEFAULT_SKILLS_PATH
from compass.resume_intake.hashing import hash_resumes
from compass.taxonomy.loader import load_taxonomy

FORMAT_BY_SUFFIX = {".pdf": "pdf", ".docx": "docx"}


def build_stub(resume_id: str, file_name: str, sha256: str, taxonomy_version: str) -> dict:
    suffix = Path(file_name).suffix.lower()
    return {
        "label_version": 1,
        "resume_id": resume_id,
        "set": "practice",
        "source": "self",
        "status": "draft",
        "file_name": file_name,
        "file_sha256": sha256,
        "format": FORMAT_BY_SUFFIX[suffix],
        "layout": "other",
        "taxonomy_version": taxonomy_version,
        "labeller": "",
        "labelled_at": datetime.now(UTC).date().isoformat(),
        "skills_present": [],
        "skills_ambiguous": [],
        "roles_fit": [],
        "roles_should_exclude": [],
        "notes": "",
    }


def make_label_stubs(resumes_dir: Path, labels_dir: Path) -> list[Path]:
    """Write one stub per resume in resumes_dir into labels_dir.

    Raises FileExistsError (with every conflicting path in .args[0]) and
    writes nothing if any target already exists.
    """
    taxonomy = load_taxonomy(DEFAULT_SKILLS_PATH, DEFAULT_ROLES_PATH)
    rows = hash_resumes(resumes_dir)

    targets = [
        (resume_id, file_name, sha256, labels_dir / f"{resume_id}.yaml")
        for resume_id, file_name, sha256 in rows
    ]

    existing = [str(target) for _, _, _, target in targets if target.exists()]
    if existing:
        raise FileExistsError(existing)

    labels_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for resume_id, file_name, sha256, target in targets:
        stub = build_stub(resume_id, file_name, sha256, taxonomy.taxonomy_version)
        with target.open("w", encoding="utf-8") as f:
            yaml.safe_dump(stub, f, sort_keys=False)
        written.append(target)

    return written
