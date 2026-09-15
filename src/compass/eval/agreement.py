"""Agreement metrics between two skill-extraction rungs (or a rung and a
reference model's output).

These are agreement metrics, not accuracy metrics: the "reference" set in
this module is not ground truth, so results are reported as agreement
between a candidate and a reference/analogue, never as correctness.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PerResumeAgreement:
    file: str
    candidate_count: int
    reference_count: int
    agreed_count: int
    jaccard: float


@dataclass
class AggregateAgreement:
    total_candidate: int
    total_reference: int
    total_agreed: int
    precision_analogue: float
    recall_analogue: float
    micro_jaccard: float


def compute_agreement(
    candidate: dict[str, set[str]],
    reference: dict[str, set[str]],
) -> tuple[list[PerResumeAgreement], AggregateAgreement]:
    candidate_keys = set(candidate)
    reference_keys = set(reference)
    if candidate_keys != reference_keys:
        mismatched = candidate_keys.symmetric_difference(reference_keys)
        raise ValueError(
            f"candidate and reference must share the same resume keys; "
            f"mismatched keys: {sorted(mismatched)}"
        )

    per_resume: list[PerResumeAgreement] = []
    total_candidate = 0
    total_reference = 0
    total_agreed = 0

    for file in sorted(candidate_keys):
        cand_set = candidate[file]
        ref_set = reference[file]
        agreed = cand_set & ref_set
        union = cand_set | ref_set
        jaccard = len(agreed) / len(union) if union else 0.0

        per_resume.append(
            PerResumeAgreement(
                file=file,
                candidate_count=len(cand_set),
                reference_count=len(ref_set),
                agreed_count=len(agreed),
                jaccard=jaccard,
            )
        )

        total_candidate += len(cand_set)
        total_reference += len(ref_set)
        total_agreed += len(agreed)

    # A zero denominator here means one rung (or the reference) found no
    # skills at all across every resume, not a bug — guard rather than
    # raise so a degenerate run still produces a readable (0.0) report.
    precision_analogue = total_agreed / total_candidate if total_candidate else 0.0
    recall_analogue = total_agreed / total_reference if total_reference else 0.0
    micro_union = total_candidate + total_reference - total_agreed
    micro_jaccard = total_agreed / micro_union if micro_union else 0.0

    aggregate = AggregateAgreement(
        total_candidate=total_candidate,
        total_reference=total_reference,
        total_agreed=total_agreed,
        precision_analogue=precision_analogue,
        recall_analogue=recall_analogue,
        micro_jaccard=micro_jaccard,
    )

    return per_resume, aggregate
