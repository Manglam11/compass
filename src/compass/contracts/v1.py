"""Compass v1 API contract.

This module is the single source of truth for the v1 request/response
schema. JSON Schema files under contracts/v1/*.schema.json are GENERATED
from these models by scripts/export_schema.py — never hand-edit them.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "v1"


class ResumeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["file"]
    content_base64: str
    mime_type: Literal[
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
    filename: str


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_roles: int = Field(default=5, ge=1, le=10)
    backend: str | None = None


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v1"]
    request_id: str
    user_id: str
    input: ResumeInput
    options: Options = Field(default_factory=Options)


class ExtractedSkill(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_id: str
    matched_alias: str
    span: tuple[int, int]


class RoleMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_id: str
    display_name: str
    score: float = Field(ge=0.0, le=1.0)
    core_ratio: float = Field(ge=0.0, le=1.0)
    matched_skills: list[str]
    missing_skills: list[str]


class ExclusionReason(str, Enum):
    CORE_GATE_FAILED = "CORE_GATE_FAILED"
    NO_SKILL_OVERLAP = "NO_SKILL_OVERLAP"
    BELOW_SCORE_FLOOR = "BELOW_SCORE_FLOOR"


class ExcludedRole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_id: str
    reason: ExclusionReason
    core_ratio: float


class Versions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomy: str
    extractor: str
    prompt: str | None = None


class Response(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v1"]
    request_id: str
    user_id: str
    generated_at: datetime
    versions: Versions
    extracted_skills: list[ExtractedSkill]
    matches: list[RoleMatch]
    excluded_roles: list[ExcludedRole]
    warnings: list[str] = Field(default_factory=list)


class ErrorCode(str, Enum):
    PARSE_FAILED = "PARSE_FAILED"
    UNSUPPORTED_MIME = "UNSUPPORTED_MIME"
    EMPTY_DOCUMENT = "EMPTY_DOCUMENT"
    TAXONOMY_LOAD_FAILED = "TAXONOMY_LOAD_FAILED"
    BACKEND_UNAVAILABLE = "BACKEND_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    detail: str
    retryable: bool


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v1"]
    request_id: str
    error: ErrorDetail
