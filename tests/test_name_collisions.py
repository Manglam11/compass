"""Tests for compass.resume_intake.collisions.

Every mapping and alias index here is synthetic — no real resume or name
list is used.
"""

from __future__ import annotations

from compass.resume_intake.collisions import Collision, find_collisions


def test_exact_alias_match_reported():
    name_map = {"prac_001": "Django Smith"}
    alias_index = {"django": "django_skill", "python": "python"}

    collisions = find_collisions(name_map, alias_index)

    assert collisions == [Collision(resume_id="prac_001", skill_id="django_skill", token_length=6)]


def test_substring_of_multiword_alias_reported():
    name_map = {"prac_008": "Carlo Rossi"}
    alias_index = {"monte carlo": "monte_carlo_simulation", "python": "python"}

    collisions = find_collisions(name_map, alias_index)

    assert collisions == [
        Collision(resume_id="prac_008", skill_id="monte_carlo_simulation", token_length=5)
    ]


def test_no_collision_when_no_overlap():
    name_map = {"prac_002": "Alex Johnson"}
    alias_index = {"python": "python", "sql": "sql"}

    assert find_collisions(name_map, alias_index) == []


def test_dedupes_same_skill_matched_by_multiple_rules():
    # "spark" collides with the single-word alias "spark" AND is a
    # substring of the multi-word alias "apache spark" — same skill either
    # way, should only be reported once.
    name_map = {"prac_003": "Spark Lee"}
    alias_index = {"spark": "spark", "apache spark": "spark"}

    collisions = find_collisions(name_map, alias_index)

    assert collisions == [Collision(resume_id="prac_003", skill_id="spark", token_length=5)]


def test_multiple_resumes_and_tokens_all_reported():
    name_map = {"prac_001": "Django Smith", "prac_002": "Alex Sql"}
    alias_index = {"django": "django_skill", "sql": "sql"}

    collisions = find_collisions(name_map, alias_index)

    assert collisions == [
        Collision(resume_id="prac_001", skill_id="django_skill", token_length=6),
        Collision(resume_id="prac_002", skill_id="sql", token_length=3),
    ]


def test_output_never_carries_the_token_or_name():
    name_map = {"prac_008": "Carlo Rossi"}
    alias_index = {"monte carlo": "monte_carlo_simulation"}

    collisions = find_collisions(name_map, alias_index)

    for field in collisions[0].__dict__.values():
        assert field not in ("Carlo", "carlo", "Rossi", "rossi", "Carlo Rossi")
