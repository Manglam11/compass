"""Tests for compass.resume_intake.names and its integration with find_pii.

No real resume or name list is used anywhere here — every fixture is
synthetic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from compass.resume_intake.names import NamesFileError, compile_name_pattern, load_names
from compass.resume_intake.pii import find_pii


def test_whole_word_boundary_sam_does_not_match_samsung():
    pattern = compile_name_pattern(["Sam"])
    text = "Samsung and Sam"
    matches = find_pii(text, pattern)

    assert [m.value for m in matches] == ["Sam"]
    assert matches[0].kind == "name"
    assert text[matches[0].start : matches[0].end] == "Sam"


def test_case_insensitive_matching():
    pattern = compile_name_pattern(["Nick Miller"])

    for text in ["NICK MILLER", "nick miller", "Nick Miller"]:
        matches = find_pii(text, pattern)
        assert [m.kind for m in matches] == ["name"], text
        assert matches[0].value.lower() == "nick miller"


def test_first_name_alone_is_matched():
    pattern = compile_name_pattern(["Nick Miller"])
    text = "Nick led the team through the migration."
    matches = find_pii(text, pattern)

    assert [m.value for m in matches] == ["Nick"]


def test_longest_match_wins_single_span():
    pattern = compile_name_pattern(["Nick Miller"])
    text = "Nick Miller led the team."
    matches = find_pii(text, pattern)

    assert len(matches) == 1
    assert matches[0].value == "Nick Miller"
    assert matches[0].kind == "name"


def test_possessive_leaves_apostrophe_s_untouched():
    pattern = compile_name_pattern(["Miller"])
    text = "Miller's project shipped on time."
    matches = find_pii(text, pattern)

    assert len(matches) == 1
    assert matches[0].value == "Miller"
    redacted = text[: matches[0].start] + "[NAME]" + text[matches[0].end :]
    assert redacted == "[NAME]'s project shipped on time."


def test_false_positive_guard_name_colliding_with_skill_tokens():
    """KNOWN LIMITATION: when a listed name collides with a skill/technology
    token (here "Django" and "Salesforce"), that token is redacted
    everywhere in the document — not just where it refers to the person.
    This destroys skill extraction for that resume. We do not attempt to
    resolve this collision; it's an accepted tradeoff of matching names by
    literal text, and this test exists to document and pin the behavior
    rather than to fix it.
    """
    pattern = compile_name_pattern(["Victoria Django Salesforce"])
    text = "Victoria Django Salesforce built a Django app using Salesforce APIs"
    matches = find_pii(text, pattern)
    values = [m.value for m in matches]

    # the person's full name is redacted as one span
    assert "Victoria Django Salesforce" in values
    # the standalone technology tokens elsewhere in the sentence are ALSO
    # caught — this is the false positive / known limitation
    assert values.count("Django") == 1
    assert values.count("Salesforce") == 1
    assert all(m.kind == "name" for m in matches)


def test_comments_and_blank_lines_ignored(tmp_path: Path):
    names_file = tmp_path / "names.txt"
    names_file.write_text(
        "# people to redact\n\nNick Miller\n\n# trailing comment\nSam\n",
        encoding="utf-8",
    )

    names = load_names(names_file)

    assert names == ["Nick Miller", "Sam"]


def test_missing_names_file_raises_clear_error(tmp_path: Path):
    missing = tmp_path / "does_not_exist.txt"

    with pytest.raises(NamesFileError):
        load_names(missing)


def test_single_token_line_matched_as_is():
    pattern = compile_name_pattern(["Aditi"])
    text = "Aditi presented the quarterly results."
    matches = find_pii(text, pattern)

    assert [m.value for m in matches] == ["Aditi"]


def test_no_name_pattern_means_no_name_matches():
    text = "Nick Miller led the team."
    matches = find_pii(text, None)

    assert matches == []
