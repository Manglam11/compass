"""Tests for compass.extract.spans."""

from __future__ import annotations

from compass.extract.spans import split_into_spans


def test_drops_short_lines():
    assert split_into_spans("short\nThis line is long enough to keep") == [
        "This line is long enough to keep"
    ]


def test_drops_blank_lines():
    text = "\n\n   \nActual content line that is long enough\n\n"
    assert split_into_spans(text) == ["Actual content line that is long enough"]


def test_boundary_exactly_min_length_is_kept():
    line = "x" * 15
    assert split_into_spans(line) == [line]


def test_boundary_one_under_min_length_is_dropped():
    line = "x" * 14
    assert split_into_spans(line) == []


def test_strips_surrounding_whitespace():
    assert split_into_spans("   Padded line with enough content   ") == [
        "Padded line with enough content"
    ]


def test_no_sentence_splitting_within_a_line():
    line = "Built REST APIs. Wrote SQL queries. Shipped to production."
    assert split_into_spans(line) == [line]


def test_realistic_multiline_resume_block():
    text = (
        "John Smith\n"
        "Senior Backend Engineer\n"
        "\n"
        "Built and maintained REST APIs serving 2M requests/day.\n"
        "Led migration from monolith to microservices architecture.\n"
        "Py\n"
        "Used PostgreSQL for primary data storage and Redis for caching.\n"
    )
    assert split_into_spans(text) == [
        "Senior Backend Engineer",
        "Built and maintained REST APIs serving 2M requests/day.",
        "Led migration from monolith to microservices architecture.",
        "Used PostgreSQL for primary data storage and Redis for caching.",
    ]


def test_empty_text_yields_no_spans():
    assert split_into_spans("") == []
