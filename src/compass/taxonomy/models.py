"""Taxonomy file format.

These models describe the on-disk shape of taxonomy/skills.yaml and
taxonomy/roles.yaml, plus the Taxonomy type produced once both files have
been loaded and cross-validated (see loader.py).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

ID_PATTERN = r"^[a-z0-9_]+$"
Weight = Annotated[int, Field(ge=1, le=5)]


class Skill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERN)
    display_name: str
    family: str = Field(pattern=ID_PATTERN)
    aliases: list[str] = Field(min_length=1)
    # Presence and length are enforced in loader._validate() as a collected
    # error rather than here, so a missing description is reported alongside
    # the other taxonomy violations instead of raising a fail-fast
    # ValidationError before cross-validation even runs.
    description: str | None = None


class SkillsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    skills: list[Skill]


class Role(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERN)
    display_name: str
    core: dict[str, Weight]
    supporting: dict[str, Weight] = Field(default_factory=dict)
    differentiator: dict[str, Weight] = Field(default_factory=dict)
    min_core_ratio: float = Field(gt=0.0, le=1.0)


class RolesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    taxonomy_version: str
    roles: list[Role]


class Taxonomy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomy_version: str
    skills: dict[str, Skill]
    roles: dict[str, Role]
    alias_index: dict[str, str]
