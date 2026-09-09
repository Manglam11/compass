"""Tests for compass.match.scorer."""

from __future__ import annotations

from compass.match.scorer import ExclusionReason, score_roles
from compass.taxonomy.models import Role, Skill, Taxonomy


def _skills(*ids: str) -> dict[str, Skill]:
    return {sid: Skill(id=sid, display_name=sid, family="language", aliases=[sid]) for sid in ids}


def _two_role_taxonomy() -> Taxonomy:
    roles = {
        "role_high_bar": Role(
            id="role_high_bar",
            display_name="Role High Bar",
            core={"a": 3, "b": 3, "c": 3},
            supporting={},
            differentiator={},
            min_core_ratio=1.0,
        ),
        "role_low_bar": Role(
            id="role_low_bar",
            display_name="Role Low Bar",
            core={"a": 3},
            supporting={"b": 2},
            differentiator={"c": 1},
            min_core_ratio=0.5,
        ),
    }
    return Taxonomy(
        taxonomy_version="test", skills=_skills("a", "b", "c"), roles=roles, alias_index={}
    )


def test_role_below_min_core_ratio_is_excluded_not_scored():
    taxonomy = _two_role_taxonomy()
    result = score_roles(["a"], taxonomy)

    excluded_ids = {excluded.role_id for excluded in result.excluded}
    matched_ids = {role.role_id for role in result.matched}

    assert "role_high_bar" in excluded_ids
    assert "role_high_bar" not in matched_ids
    reason = next(e.reason for e in result.excluded if e.role_id == "role_high_bar")
    assert reason == ExclusionReason.CORE_GATE_FAILED


def test_scoring_is_deterministic_for_same_input():
    taxonomy = _two_role_taxonomy()
    first = score_roles(["a", "b", "c"], taxonomy)
    second = score_roles(["a", "b", "c"], taxonomy)
    assert first == second
    assert repr(first) == repr(second)


def test_results_capped_at_five():
    roles = {
        f"role_{i}": Role(
            id=f"role_{i}",
            display_name=f"Role {i}",
            core={"s": 3},
            supporting={},
            differentiator={},
            min_core_ratio=0.5,
        )
        for i in range(7)
    }
    taxonomy = Taxonomy(taxonomy_version="test", skills=_skills("s"), roles=roles, alias_index={})

    result = score_roles(["s"], taxonomy)
    assert len(result.matched) == 5
    assert len(result.excluded) == 0
