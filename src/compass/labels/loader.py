"""Loads and cross-validates resume label files against the taxonomy.

All violations are collected up front and raised together in a single
LabelError, rather than failing on the first one found.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml
from pydantic import ValidationError

from compass.labels.schema import ResumeLabel
from compass.taxonomy.loader import load_taxonomy
from compass.taxonomy.models import Taxonomy

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_SKILLS_PATH = REPO_ROOT / "taxonomy" / "skills.yaml"
DEFAULT_ROLES_PATH = REPO_ROOT / "taxonomy" / "roles.yaml"

RESUME_ID_PREFIX_TO_SET = {"prac": "practice", "exam": "exam"}


class LabelError(Exception):
    pass


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _find_duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


def load_labels(directory: Path, taxonomy: Taxonomy | None = None) -> list[ResumeLabel]:
    if taxonomy is None:
        taxonomy = load_taxonomy(DEFAULT_SKILLS_PATH, DEFAULT_ROLES_PATH)

    label_paths = sorted(directory.rglob("*.yaml"))

    errors: list[str] = []
    labels: list[ResumeLabel] = []
    file_names: list[str] = []

    for path in label_paths:
        try:
            data = _load_yaml(path)
            label = ResumeLabel.model_validate(data)
        except (ValidationError, yaml.YAMLError) as exc:
            errors.append(f"{path.name}: schema violation: {exc}")
            continue

        for skill_id in label.skills_present:
            if skill_id not in taxonomy.skills:
                errors.append(f"{path.name}: unknown skill id in skills_present: '{skill_id}'")
        for skill_id in label.skills_ambiguous:
            if skill_id not in taxonomy.skills:
                errors.append(f"{path.name}: unknown skill id in skills_ambiguous: '{skill_id}'")

        for role_id in label.roles_fit:
            if role_id not in taxonomy.roles:
                errors.append(f"{path.name}: unknown role id in roles_fit: '{role_id}'")
        for role_id in label.roles_should_exclude:
            if role_id not in taxonomy.roles:
                errors.append(f"{path.name}: unknown role id in roles_should_exclude: '{role_id}'")

        for skill_id in sorted(set(label.skills_present) & set(label.skills_ambiguous)):
            errors.append(
                f"{path.name}: skill '{skill_id}' appears in both skills_present and "
                f"skills_ambiguous"
            )

        for role_id in sorted(set(label.roles_fit) & set(label.roles_should_exclude)):
            errors.append(
                f"{path.name}: role '{role_id}' appears in both roles_fit and roles_should_exclude"
            )

        prefix = label.resume_id.split("_")[0]
        if RESUME_ID_PREFIX_TO_SET.get(prefix) != label.set:
            errors.append(
                f"{path.name}: resume_id prefix '{prefix}_' does not match set '{label.set}'"
            )

        if label.taxonomy_version != taxonomy.taxonomy_version:
            errors.append(
                f"{path.name}: taxonomy_version '{label.taxonomy_version}' does not match "
                f"current taxonomy_version '{taxonomy.taxonomy_version}'"
            )

        labels.append(label)
        file_names.append(path.name)

    resume_id_files: dict[str, list[str]] = defaultdict(list)
    for label, name in zip(labels, file_names):
        resume_id_files[label.resume_id].append(name)
    for resume_id in sorted(_find_duplicates([label.resume_id for label in labels])):
        files = ", ".join(resume_id_files[resume_id])
        errors.append(f"duplicate resume_id '{resume_id}' across files: {files}")

    sha256_files: dict[str, list[str]] = defaultdict(list)
    for label, name in zip(labels, file_names):
        sha256_files[label.file_sha256].append(name)
    for sha256, names in sorted(sha256_files.items()):
        if len(names) > 1:
            errors.append(f"duplicate file_sha256 '{sha256}' across files: {', '.join(names)}")

    if errors:
        raise LabelError("\n".join(f"- {error}" for error in errors))

    return labels
