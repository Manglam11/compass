"""Tests for compass.mining.prompt_builder.

No LLM call here -- this only tests the constructed prompt string.
"""

from __future__ import annotations

import re
from pathlib import Path

from compass.mining.corpus_loader import CorpusResume
from compass.mining.prompt_builder import build_mining_prompt
from compass.taxonomy.loader import load_taxonomy

REPO_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = load_taxonomy(
    REPO_ROOT / "taxonomy" / "skills.yaml", REPO_ROOT / "taxonomy" / "roles.yaml"
)


def _resume(resume_id: str, category: str, text: str) -> CorpusResume:
    return CorpusResume(resume_id=resume_id, category=category, text=text)


def test_prompt_contains_every_skill_id_exactly_once():
    # Each skill_id must head exactly one "skill_id: <aliases>" vocabulary
    # line. This is distinct from a whole-prompt substring count: an id like
    # "airflow" legitimately reappears inside other aliases of the same
    # skill (e.g. "apache airflow"), so the invariant that matters is one
    # vocabulary entry per id, not one occurrence of the word anywhere.
    batch = [_resume("0000", "Data Science", "UNIQUE_MARKER built things.")]
    prompt = build_mining_prompt(batch, TAXONOMY)

    for skill_id in sorted(TAXONOMY.skills):
        matches = re.findall(rf"^{re.escape(skill_id)}: ", prompt, flags=re.MULTILINE)
        assert len(matches) == 1, f"{skill_id!r} headed {len(matches)} vocabulary lines, expected 1"


def test_prompt_contains_each_resumes_text_and_id():
    batch = [
        _resume("0000", "Data Science", "UNIQUE_MARKER_ONE about pandas usage."),
        _resume("0001", "DevOps", "UNIQUE_MARKER_TWO about pipelines."),
    ]
    prompt = build_mining_prompt(batch, TAXONOMY)

    assert "UNIQUE_MARKER_ONE about pandas usage." in prompt
    assert "UNIQUE_MARKER_TWO about pipelines." in prompt
    assert "0000" in prompt
    assert "0001" in prompt


def test_prompt_contains_output_schema_instruction():
    batch = [_resume("0000", "Data Science", "some text")]
    prompt = build_mining_prompt(batch, TAXONOMY)

    assert "resume_id" in prompt
    assert "skill_id" in prompt
    assert "quoted_phrase" in prompt
    assert "suggested_name" in prompt
    assert "NEW" in prompt
    assert "JSON" in prompt


def test_prompt_lists_existing_aliases_for_closed_vocabulary_check():
    batch = [_resume("0000", "Data Science", "some text")]
    prompt = build_mining_prompt(batch, TAXONOMY)

    python_aliases = [a for a in TAXONOMY.skills["python"].aliases if a != "python"]
    assert python_aliases, "fixture assumption: python has aliases beyond its own id"
    for alias in python_aliases:
        assert alias in prompt
