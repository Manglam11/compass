"""Scores rung 1 (gazetteer) and rung 2 (embeddings) extracted skills for
grounding in their source resume text, using the ragas AspectCritic
wrapper in compass.eval.grounding.

Requires ANTHROPIC_API_KEY to run for real. With no key set, this prints
a one-line message and exits 1 rather than crashing with a raw
KeyError/traceback -- that is the expected outcome until a key is
available. Output is skill ids and grounding scores only, never resume
text.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from compass.eval.extraction import load_resume_extractions
from compass.eval.grounding import (
    AggregateGrounding,
    PerResumeGrounding,
    build_grounding_metric,
    compute_grounding_report,
    score_skill_grounding,
)
from compass.taxonomy.loader import load_taxonomy

ROOT = Path(__file__).resolve().parent.parent
TAXONOMY_DIR = ROOT / "taxonomy"
STRIPPED_DIR = ROOT / "resumes_stripped_v2"

ANTHROPIC_MODEL = "claude-sonnet-4-5-20250929"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--own-resume",
        type=Path,
        required=True,
        help="Path to the own-resume file (mapped to the my_resume reference key).",
    )
    return parser.parse_args()


def build_resume_paths(own_resume: Path) -> dict[str, Path]:
    return {
        "prac_001": STRIPPED_DIR / "prac_001.pdf",
        "prac_006": STRIPPED_DIR / "prac_006.pdf",
        "prac_007": STRIPPED_DIR / "prac_007.docx",
        "my_resume": own_resume,
        "prac_014": STRIPPED_DIR / "prac_014.pdf",
        "prac_018": STRIPPED_DIR / "prac_018.pdf",
    }


def print_table(per_resume: list[PerResumeGrounding], aggregate: AggregateGrounding) -> None:
    print(f"  {'file':<12} {'skills':>6} {'grounded':>8} {'pass_rate':>9}")
    for row in per_resume:
        print(
            f"  {row.file:<12} {row.skill_count:>6} {row.grounded_count:>8} {row.pass_rate:>9.2f}"
        )
    print(
        f"  aggregate: total_skills={aggregate.total_skills} "
        f"total_grounded={aggregate.total_grounded} "
        f"pass_rate={aggregate.pass_rate:.2f}"
    )


def main() -> int:
    args = parse_args()
    taxonomy = load_taxonomy(TAXONOMY_DIR / "skills.yaml", TAXONOMY_DIR / "roles.yaml")
    resume_paths = build_resume_paths(args.own_resume)

    rung1_skills, rung2_skills, texts = load_resume_extractions(taxonomy, resume_paths)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set -- cannot run grounding against a real model yet")
        return 1

    import anthropic
    from ragas.llms import llm_factory

    client = anthropic.Anthropic(api_key=api_key)
    llm = llm_factory(model=ANTHROPIC_MODEL, provider="anthropic", client=client)
    metric = build_grounding_metric(llm)

    def score_fn(skill: str, resume_text: str) -> float:
        return score_skill_grounding(metric, skill, resume_text)

    rung1_per_resume, rung1_aggregate = compute_grounding_report(score_fn, rung1_skills, texts)
    print("rung 1 grounding:")
    print_table(rung1_per_resume, rung1_aggregate)

    rung2_per_resume, rung2_aggregate = compute_grounding_report(score_fn, rung2_skills, texts)
    print()
    print("rung 2 grounding:")
    print_table(rung2_per_resume, rung2_aggregate)

    return 0


if __name__ == "__main__":
    sys.exit(main())
