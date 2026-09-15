"""Wrapper around ragas's AspectCritic metric for scoring whether an
extracted skill is grounded in a single resume text span.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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


GROUNDING_THRESHOLD = 0.5


@dataclass
class PerResumeGrounding:
    file: str
    skill_count: int
    grounded_count: int
    pass_rate: float


@dataclass
class AggregateGrounding:
    total_skills: int
    total_grounded: int
    pass_rate: float


def compute_grounding_report(
    score_fn: Callable[[str, str], float],
    skills_by_resume: dict[str, set[str]],
    text_by_resume: dict[str, str],
) -> tuple[list[PerResumeGrounding], AggregateGrounding]:
    skills_keys = set(skills_by_resume)
    text_keys = set(text_by_resume)
    if skills_keys != text_keys:
        mismatched = skills_keys.symmetric_difference(text_keys)
        raise ValueError(
            f"skills_by_resume and text_by_resume must share the same resume keys; "
            f"mismatched keys: {sorted(mismatched)}"
        )

    per_resume: list[PerResumeGrounding] = []
    total_skills = 0
    total_grounded = 0

    for file in sorted(skills_keys):
        skills = skills_by_resume[file]
        text = text_by_resume[file]
        grounded_count = sum(1 for skill in skills if score_fn(skill, text) >= GROUNDING_THRESHOLD)

        # An empty skill set means the rung found nothing for that resume,
        # not a bug — guard rather than raise so the report stays readable.
        pass_rate = grounded_count / len(skills) if skills else 0.0

        per_resume.append(
            PerResumeGrounding(
                file=file,
                skill_count=len(skills),
                grounded_count=grounded_count,
                pass_rate=pass_rate,
            )
        )

        total_skills += len(skills)
        total_grounded += grounded_count

    aggregate_pass_rate = total_grounded / total_skills if total_skills else 0.0

    aggregate = AggregateGrounding(
        total_skills=total_skills,
        total_grounded=total_grounded,
        pass_rate=aggregate_pass_rate,
    )

    return per_resume, aggregate
