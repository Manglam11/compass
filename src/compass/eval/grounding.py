"""Wrapper around ragas's AspectCritic metric for scoring whether an
extracted skill is grounded in a single resume text span.
"""

from __future__ import annotations

from ragas.dataset_schema import SingleTurnSample
from ragas.metrics import AspectCritic

GROUNDING_DEFINITION = (
    "Given a resume text span as context and an extracted skill as the "
    "response, judge whether the skill is directly supported by the "
    "context. Return 1 if the context contains an explicit statement, "
    "claim, or description that substantiates the skill. Return 0 if the "
    "skill is not mentioned in the context, is only implied without a "
    "supporting claim, or appears solely as a heading or list item with no "
    "accompanying statement that backs it up."
)


def build_grounding_metric(llm) -> AspectCritic:
    return AspectCritic(
        name="skill_grounded_in_resume",
        definition=GROUNDING_DEFINITION,
        llm=llm,
    )


def score_skill_grounding(metric: AspectCritic, skill: str, resume_span: str) -> float:
    sample = SingleTurnSample(response=skill, retrieved_contexts=[resume_span])
    return metric.single_turn_score(sample)
