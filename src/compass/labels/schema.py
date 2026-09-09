"""Resume label file format.

Describes the on-disk shape of a single hand-labelled resume record under
labels/practice/ or labels/exam/. Cross-file and cross-taxonomy validation
happens in loader.py, not here.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResumeLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label_version: Literal[1]
    resume_id: str = Field(pattern=r"^(prac|exam)_\d{3}$")
    set: Literal["practice", "exam"]
    source: Literal["self", "lead"]
    file_name: str
    file_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    format: Literal["pdf", "docx"]
    layout: Literal["single_column", "two_column", "scan", "canva", "other"]
    taxonomy_version: str
    labeller: str
    labelled_at: date
    skills_present: list[str] = Field(min_length=1)
    skills_ambiguous: list[str] = Field(default_factory=list)
    roles_fit: list[str] = Field(min_length=1)
    roles_should_exclude: list[str] = Field(default_factory=list)
    notes: str = ""
