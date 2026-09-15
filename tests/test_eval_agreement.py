"""Tests for compass.eval.agreement.

The S06 reference fixture below is not invented: OPUS_REFERENCE is the
Session 06 recorded reference-model output (see scripts/rung_compare.py),
and CANDIDATE is a hand-built rung-1-shaped set of skill ids chosen so
that comparing it against OPUS_REFERENCE reproduces the exact Session 06
aggregate (S06_CANARY in scripts/rung_compare.py): total_candidate=61,
total_reference=64, total_agreed=51, micro_jaccard=0.69.
"""

from __future__ import annotations

import pytest

from compass.eval.agreement import compute_agreement

OPUS_REFERENCE: dict[str, set[str]] = {
    "prac_001": {
        "api_integration",
        "ci_cd",
        "data_visualisation",
        "git",
        "javascript",
        "linux",
        "logging_monitoring",
        "mysql",
        "rest_api",
        "sql",
    },
    "prac_006": {"computer_vision", "python", "pytorch"},
    "prac_007": {"aws", "ci_cd", "git", "javascript"},
    "my_resume": {
        "agent_frameworks",
        "api_integration",
        "ci_cd",
        "data_visualisation",
        "django",
        "docker",
        "fastapi",
        "feature_engineering",
        "git",
        "llm_integration",
        "logging_monitoring",
        "mlops",
        "model_evaluation",
        "model_serving",
        "mysql",
        "nlp",
        "numpy",
        "pandas",
        "postgresql",
        "python",
        "pytorch",
        "rag",
        "scikit_learn",
        "selenium",
        "sql",
        "statistics",
        "streamlit",
        "time_series",
        "unit_testing",
        "vector_db",
        "web_scraping",
        "xgboost",
    },
    "prac_014": {
        "api_integration",
        "git",
        "javascript",
        "postgresql",
        "rest_api",
        "sql",
        "web_scraping",
    },
    "prac_018": {
        "api_integration",
        "beautifulsoup",
        "flask",
        "javascript",
        "linux",
        "logging_monitoring",
        "python",
        "web_scraping",
    },
}

# Hand-built to hit agreed=8/candidate=9, agreed=3/candidate=3,
# agreed=3/candidate=3, agreed=28/candidate=30, agreed=6/candidate=6,
# agreed=3/candidate=10 -> totals candidate=61, agreed=51.
S06_SHAPED_CANDIDATE: dict[str, set[str]] = {
    "prac_001": {
        "api_integration",
        "ci_cd",
        "data_visualisation",
        "git",
        "javascript",
        "linux",
        "logging_monitoring",
        "sql",
        "docker",  # not in reference
    },
    "prac_006": {"computer_vision", "python", "pytorch"},
    "prac_007": {"ci_cd", "git", "javascript"},
    "my_resume": {
        "agent_frameworks",
        "api_integration",
        "ci_cd",
        "data_visualisation",
        "django",
        "docker",
        "fastapi",
        "feature_engineering",
        "git",
        "llm_integration",
        "logging_monitoring",
        "mlops",
        "model_evaluation",
        "model_serving",
        "mysql",
        "nlp",
        "numpy",
        "pandas",
        "postgresql",
        "python",
        "pytorch",
        "rag",
        "scikit_learn",
        "sql",
        "statistics",
        "vector_db",
        "web_scraping",
        "xgboost",
        "kubernetes",  # not in reference
        "terraform",  # not in reference
    },
    "prac_014": {"api_integration", "git", "javascript", "postgresql", "rest_api", "sql"},
    "prac_018": {
        "api_integration",
        "javascript",
        "python",
        "aws",
        "docker",
        "kubernetes",
        "terraform",
        "git",
        "sql",
        "fastapi",
    },
}


def test_s06_reference_fixture_reproduces_session_06_aggregate():
    per_resume, aggregate = compute_agreement(S06_SHAPED_CANDIDATE, OPUS_REFERENCE)

    assert aggregate.total_candidate == 61
    assert aggregate.total_reference == 64
    assert aggregate.total_agreed == 51
    assert aggregate.micro_jaccard == pytest.approx(0.69, abs=0.01)

    by_file = {row.file: row for row in per_resume}
    assert by_file["prac_001"].agreed_count == 8
    assert by_file["prac_001"].candidate_count == 9
    assert by_file["prac_018"].agreed_count == 3
    assert by_file["prac_018"].candidate_count == 10


def test_equal_sets_have_jaccard_one():
    candidate = {"a": {"python", "docker"}, "b": {"sql"}, "c": {"git"}}
    reference = {"a": {"python", "docker"}, "b": {"sql"}, "c": {"git"}}

    per_resume, aggregate = compute_agreement(candidate, reference)

    assert all(row.jaccard == 1.0 for row in per_resume)
    assert aggregate.total_candidate == 4
    assert aggregate.total_reference == 4
    assert aggregate.total_agreed == 4
    assert aggregate.precision_analogue == 1.0
    assert aggregate.recall_analogue == 1.0
    assert aggregate.micro_jaccard == 1.0


def test_disjoint_sets_have_jaccard_zero():
    candidate = {"a": {"python"}, "b": {"docker"}, "c": {"sql"}}
    reference = {"a": {"java"}, "b": {"terraform"}, "c": {"git"}}

    per_resume, aggregate = compute_agreement(candidate, reference)

    assert all(row.jaccard == 0.0 for row in per_resume)
    assert all(row.agreed_count == 0 for row in per_resume)
    assert aggregate.total_agreed == 0
    assert aggregate.precision_analogue == 0.0
    assert aggregate.recall_analogue == 0.0
    assert aggregate.micro_jaccard == 0.0


def test_empty_candidate_set_guards_precision_analogue():
    candidate = {"a": set(), "b": set(), "c": set()}
    reference = {"a": {"python"}, "b": {"docker"}, "c": set()}

    per_resume, aggregate = compute_agreement(candidate, reference)

    by_file = {row.file: row for row in per_resume}
    assert by_file["a"].jaccard == 0.0
    assert by_file["c"].jaccard == 0.0  # both empty: guarded, not ZeroDivisionError

    assert aggregate.total_candidate == 0
    assert aggregate.precision_analogue == 0.0  # guarded, not ZeroDivisionError
    assert aggregate.recall_analogue == 0.0
    assert aggregate.micro_jaccard == 0.0


def test_mismatched_keys_raise_value_error():
    candidate = {"a": {"python"}, "b": {"docker"}}
    reference = {"a": {"python"}, "c": {"docker"}}

    with pytest.raises(ValueError, match="b"):
        compute_agreement(candidate, reference)
