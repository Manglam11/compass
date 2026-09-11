"""Loads and cross-validates taxonomy/skills.yaml + taxonomy/roles.yaml.

All violations are collected up front and raised together in a single
TaxonomyError, rather than failing on the first one found.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from compass.taxonomy.models import Role, RolesFile, Skill, SkillsFile, Taxonomy

WEIGHT_BUCKETS = ("core", "supporting", "differentiator")


class TaxonomyError(Exception):
    pass


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _find_duplicates(ids: list[str]) -> set[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for value in ids:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


def _validate(skills_file: SkillsFile, roles_file: RolesFile) -> list[str]:
    errors: list[str] = []

    skill_ids = [skill.id for skill in skills_file.skills]
    for dupe in sorted(_find_duplicates(skill_ids)):
        errors.append(f"duplicate skill id: '{dupe}'")

    role_ids = [role.id for role in roles_file.roles]
    for dupe in sorted(_find_duplicates(role_ids)):
        errors.append(f"duplicate role id: '{dupe}'")

    alias_owners: dict[str, list[str]] = {}
    for skill in skills_file.skills:
        for alias in skill.aliases:
            if alias != alias.strip() or alias != alias.lower():
                errors.append(f"skill '{skill.id}' has non-lowercase or untrimmed alias: '{alias}'")
            alias_owners.setdefault(alias, []).append(skill.id)

    for alias, owners in sorted(alias_owners.items()):
        if len(owners) > 1:
            owner_list = ", ".join(sorted(owners))
            errors.append(f"alias '{alias}' is used by multiple skills: {owner_list}")

    for skill in skills_file.skills:
        if skill.id not in skill.aliases:
            errors.append(f"skill '{skill.id}' is missing its own id from its aliases list")

    for skill in skills_file.skills:
        if skill.description is None:
            errors.append(f"skill '{skill.id}' is missing a description")
        elif not (20 <= len(skill.description) <= 200):
            errors.append(
                f"skill '{skill.id}' has description of length {len(skill.description)}, "
                "must be between 20 and 200 characters"
            )

    known_skill_ids = set(skill_ids)
    for role in roles_file.roles:
        for bucket in WEIGHT_BUCKETS:
            for skill_id in getattr(role, bucket):
                if skill_id not in known_skill_ids:
                    errors.append(
                        f"role '{role.id}' bucket '{bucket}' references unknown skill id: "
                        f"'{skill_id}'"
                    )

    for role in roles_file.roles:
        bucket_membership: dict[str, list[str]] = {}
        for bucket in WEIGHT_BUCKETS:
            for skill_id in getattr(role, bucket):
                bucket_membership.setdefault(skill_id, []).append(bucket)
        for skill_id, buckets in sorted(bucket_membership.items()):
            if len(buckets) > 1:
                bucket_list = ", ".join(buckets)
                errors.append(
                    f"role '{role.id}' has skill '{skill_id}' in more than one weight "
                    f"bucket: {bucket_list}"
                )

    for role in roles_file.roles:
        if not role.core:
            errors.append(f"role '{role.id}' has an empty core bucket")

    if skills_file.version != roles_file.taxonomy_version:
        errors.append(
            f"skills.yaml version '{skills_file.version}' does not match roles.yaml "
            f"taxonomy_version '{roles_file.taxonomy_version}'"
        )
    if roles_file.version != roles_file.taxonomy_version:
        errors.append(
            f"roles.yaml version '{roles_file.version}' does not match roles.yaml "
            f"taxonomy_version '{roles_file.taxonomy_version}'"
        )

    return errors


def _build_alias_index(skills_file: SkillsFile) -> dict[str, str]:
    alias_index: dict[str, str] = {}
    for skill in skills_file.skills:
        for alias in skill.aliases:
            alias_index[alias] = skill.id
    return alias_index


def load_taxonomy(skills_path: Path, roles_path: Path) -> Taxonomy:
    skills_file = SkillsFile.model_validate(_load_yaml(skills_path))
    roles_file = RolesFile.model_validate(_load_yaml(roles_path))

    errors = _validate(skills_file, roles_file)
    if errors:
        raise TaxonomyError("\n".join(f"- {error}" for error in errors))

    skills: dict[str, Skill] = {skill.id: skill for skill in skills_file.skills}
    roles: dict[str, Role] = {role.id: role for role in roles_file.roles}
    alias_index = _build_alias_index(skills_file)

    return Taxonomy(
        taxonomy_version=roles_file.taxonomy_version,
        skills=skills,
        roles=roles,
        alias_index=alias_index,
    )
