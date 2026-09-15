"""Tests for compass.eval.grounding.

The seam we mock is ragas.llms.base.InstructorBaseRagasLLM.generate: when an
AspectCritic's llm is an InstructorBaseRagasLLM, ragas's PydanticPrompt.generate
(ragas/prompt/pydantic_prompt.py) calls llm.generate(prompt=<str>,
response_model=AspectCriticOutput) directly (sync path, is_async=False) instead
of going through a LangChain agenerate_prompt() or BaseRagasLLM.generate()
call. Mocking there proves the wrapper is wired to a real ragas call path, not
just that single_turn_score returns whatever we tell it to.
"""

from __future__ import annotations

import pytest
from ragas.llms.base import InstructorBaseRagasLLM

from compass.eval.grounding import (
    GROUNDING_DEFINITION,
    build_grounding_metric,
    compute_grounding_report,
    score_skill_grounding,
)


class FakeInstructorLLM(InstructorBaseRagasLLM):
    """Stands in for an instructor-patched Anthropic client."""

    def __init__(self, verdict: int) -> None:
        self.verdict = verdict
        self.is_async = False
        self.prompts_seen: list[str] = []

    def generate(self, prompt, response_model):
        self.prompts_seen.append(prompt)
        return response_model(reason="fake reason", verdict=self.verdict)

    async def agenerate(self, prompt, response_model):
        raise NotImplementedError("test LLM is sync-only")


def test_build_grounding_metric_has_expected_name_and_definition():
    metric = build_grounding_metric(FakeInstructorLLM(verdict=1))
    assert metric.name == "skill_grounded_in_resume"
    assert metric.definition == GROUNDING_DEFINITION


def test_score_skill_grounding_grounded():
    llm = FakeInstructorLLM(verdict=1)
    metric = build_grounding_metric(llm)

    score = score_skill_grounding(metric, "Python", "Built ETL pipelines in Python.")

    assert score == 1.0
    assert llm.prompts_seen


def test_score_skill_grounding_not_grounded():
    llm = FakeInstructorLLM(verdict=0)
    metric = build_grounding_metric(llm)

    score = score_skill_grounding(metric, "Kubernetes", "Managed a team of five engineers.")

    assert score == 0.0
    assert llm.prompts_seen


def test_compute_grounding_report_all_grounded():
    skills_by_resume = {"a": {"python", "sql"}, "b": {"docker"}}
    text_by_resume = {"a": "text a", "b": "text b"}

    per_resume, aggregate = compute_grounding_report(
        lambda skill, text: 1.0, skills_by_resume, text_by_resume
    )

    assert all(row.pass_rate == 1.0 for row in per_resume)
    assert aggregate.total_skills == 3
    assert aggregate.total_grounded == 3
    assert aggregate.pass_rate == 1.0


def test_compute_grounding_report_none_grounded():
    skills_by_resume = {"a": {"python", "sql"}, "b": {"docker"}}
    text_by_resume = {"a": "text a", "b": "text b"}

    per_resume, aggregate = compute_grounding_report(
        lambda skill, text: 0.0, skills_by_resume, text_by_resume
    )

    assert all(row.pass_rate == 0.0 for row in per_resume)
    assert aggregate.total_skills == 3
    assert aggregate.total_grounded == 0
    assert aggregate.pass_rate == 0.0


def test_compute_grounding_report_mixed():
    skills_by_resume = {"a": {"python", "sql", "docker"}}
    text_by_resume = {"a": "text a"}
    grounded = {"python", "sql"}

    per_resume, aggregate = compute_grounding_report(
        lambda skill, text: 1.0 if skill in grounded else 0.0, skills_by_resume, text_by_resume
    )

    assert per_resume[0].skill_count == 3
    assert per_resume[0].grounded_count == 2
    assert per_resume[0].pass_rate == pytest.approx(2 / 3)
    assert aggregate.total_skills == 3
    assert aggregate.total_grounded == 2
    assert aggregate.pass_rate == pytest.approx(2 / 3)


def test_compute_grounding_report_empty_skill_set_guards_pass_rate():
    skills_by_resume = {"a": set(), "b": {"python"}}
    text_by_resume = {"a": "text a", "b": "text b"}

    per_resume, aggregate = compute_grounding_report(
        lambda skill, text: 1.0, skills_by_resume, text_by_resume
    )

    by_file = {row.file: row for row in per_resume}
    assert by_file["a"].skill_count == 0
    assert by_file["a"].pass_rate == 0.0  # guarded, not ZeroDivisionError
    assert aggregate.total_skills == 1
    assert aggregate.pass_rate == 1.0


def test_compute_grounding_report_mismatched_keys_raise_value_error():
    skills_by_resume = {"a": {"python"}, "b": {"docker"}}
    text_by_resume = {"a": "text a", "c": "text c"}

    with pytest.raises(ValueError, match="b"):
        compute_grounding_report(lambda skill, text: 1.0, skills_by_resume, text_by_resume)
