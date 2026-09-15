"""Tests for the rung 3 pieces of compass.eval.extraction: run_rung3,
latency_summary, get_server_version, load_resume_texts.

compass.extract.ollama_llm.extract_skills is mocked throughout -- no live
model, no network, no Docker.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from compass.eval.extraction import (
    get_server_version,
    latency_summary,
    load_resume_texts,
    run_rung3,
)
from compass.extract import ollama_llm
from compass.extract.ollama_llm import Rung3ExtractionError
from compass.taxonomy.loader import load_taxonomy

REPO_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = load_taxonomy(
    REPO_ROOT / "taxonomy" / "skills.yaml", REPO_ROOT / "taxonomy" / "roles.yaml"
)

TEXTS = {"prac_001": "resume one text", "prac_006": "resume two text"}


def test_run_rung3_does_one_untimed_warmup_call_before_timed_calls(monkeypatch):
    calls: list[tuple[str, str | None]] = []

    def fake_extract_skills(text, taxonomy, *, model=None):
        calls.append((text, model))
        return ["python"]

    monkeypatch.setattr(ollama_llm, "extract_skills", fake_extract_skills)

    result = run_rung3(TAXONOMY, TEXTS, model="phi4-mini")

    # warm-up call first, then one call per resume, all with the given model
    assert len(calls) == 1 + len(TEXTS)
    assert all(model == "phi4-mini" for _text, model in calls)
    warmup_text, _ = calls[0]
    assert warmup_text not in TEXTS.values()
    assert result.skills_by_resume == {"prac_001": {"python"}, "prac_006": {"python"}}
    assert result.failures == {}


def test_run_rung3_excludes_failing_resume_and_records_failure_message(monkeypatch):
    call_count = {"n": 0}

    def fake_extract_skills(text, taxonomy, *, model=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return []  # warm-up call
        if text == "resume one text":
            raise Rung3ExtractionError("Ollama returned an empty response")
        return ["sql"]

    monkeypatch.setattr(ollama_llm, "extract_skills", fake_extract_skills)

    result = run_rung3(TAXONOMY, TEXTS, model=None)

    assert "prac_001" not in result.skills_by_resume
    assert result.failures == {"prac_001": "Ollama returned an empty response"}
    assert result.skills_by_resume == {"prac_006": {"sql"}}


def test_run_rung3_never_folds_a_failure_into_an_empty_skill_list(monkeypatch):
    """A failed resume must be ABSENT from skills_by_resume, never present
    as an empty set -- an empty set there would be indistinguishable from
    "the model found nothing".
    """

    def fake_extract_skills(text, taxonomy, *, model=None):
        if text == "resume one text":
            raise Rung3ExtractionError("boom")
        return []

    monkeypatch.setattr(ollama_llm, "extract_skills", fake_extract_skills)

    result = run_rung3(TAXONOMY, TEXTS, model=None)

    assert "prac_001" not in result.skills_by_resume
    assert "prac_001" in result.failures


def test_latency_summary_median_and_max_on_fixed_timings():
    seconds = {"a": 1.0, "b": 3.0, "c": 2.0}
    median, maximum = latency_summary(seconds)
    assert median == 2.0
    assert maximum == 3.0


def test_latency_summary_empty_is_zero():
    assert latency_summary({}) == (0.0, 0.0)


def test_get_server_version_returns_none_when_unreachable(monkeypatch):
    import urllib.error

    def fake_urlopen(url, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert get_server_version("http://127.0.0.1:11434") is None


def test_get_server_version_parses_response(monkeypatch):
    import io

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    def fake_urlopen(url, timeout=None):
        assert url == "http://127.0.0.1:11434/api/version"
        return FakeResponse(b'{"version": "0.5.1"}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert get_server_version("http://127.0.0.1:11434") == "0.5.1"


def test_load_resume_texts_maps_key_to_text(monkeypatch, tmp_path):
    fake_path = tmp_path / "resume.pdf"
    fake_path.write_bytes(b"not a real pdf")

    monkeypatch.setattr(
        "compass.eval.extraction.extract_resume_text", lambda path: f"text for {path.name}"
    )

    result = load_resume_texts({"my_resume": fake_path})

    assert result == {"my_resume": "text for resume.pdf"}


def test_load_resume_texts_wraps_failures(monkeypatch, tmp_path):
    fake_path = tmp_path / "resume.pdf"
    fake_path.write_bytes(b"not a real pdf")

    def boom(path):
        raise ValueError("bad pdf")

    monkeypatch.setattr("compass.eval.extraction.extract_resume_text", boom)

    with pytest.raises(RuntimeError, match="my_resume"):
        load_resume_texts({"my_resume": fake_path})
