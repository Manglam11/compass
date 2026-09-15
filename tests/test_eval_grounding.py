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

from ragas.llms.base import InstructorBaseRagasLLM

from compass.eval.grounding import (
    GROUNDING_DEFINITION,
    build_grounding_metric,
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
