"""Deterministic rule-based scoring of a candidate's skills against roles.

No randomness, no model calls: given the same found_skills and taxonomy,
score_roles always returns byte-identical output.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from compass.taxonomy.models import Role, Taxonomy

WEIGHT_BUCKETS = ("core", "supporting", "differentiator")
TOP_N = 5


class ExclusionReason(str, Enum):
    CORE_GATE_FAILED = "core_gate_failed"


@dataclass(frozen=True)
class RoleResult:
    role_id: str
    score: float
    matched_skills: list[str]
    missing_skills: list[str]


@dataclass(frozen=True)
class ExcludedRole:
    role_id: str
    reason: ExclusionReason


@dataclass(frozen=True)
class ScoreResult:
    matched: list[RoleResult]
    excluded: list[ExcludedRole]


def _weighted_skills(role: Role) -> dict[str, int]:
    weights: dict[str, int] = {}
    for bucket in WEIGHT_BUCKETS:
        weights.update(getattr(role, bucket))
    return weights


def score_roles(found_skills: list[str], taxonomy: Taxonomy) -> ScoreResult:
    found = set(found_skills)
    matched: list[RoleResult] = []
    excluded: list[ExcludedRole] = []

    for role in taxonomy.roles.values():
        core_matched = sum(1 for skill_id in role.core if skill_id in found)
        core_ratio = core_matched / len(role.core)

        if core_ratio < role.min_core_ratio:
            excluded.append(ExcludedRole(role_id=role.id, reason=ExclusionReason.CORE_GATE_FAILED))
            continue

        weights = _weighted_skills(role)
        weighted_total = sum(weights.values())
        weighted_matched = sum(weight for skill_id, weight in weights.items() if skill_id in found)

        matched.append(
            RoleResult(
                role_id=role.id,
                score=weighted_matched / weighted_total,
                matched_skills=sorted(skill_id for skill_id in weights if skill_id in found),
                missing_skills=sorted(skill_id for skill_id in weights if skill_id not in found),
            )
        )

    matched.sort(key=lambda result: (-result.score, result.role_id))
    excluded.sort(key=lambda item: item.role_id)

    return ScoreResult(matched=matched[:TOP_N], excluded=excluded)
