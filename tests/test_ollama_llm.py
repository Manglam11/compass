"""Tests for compass.extract.ollama_llm.

The Ollama client is fully mocked: no live model, no network, no Docker in
this suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from compass.extract import ollama_llm
from compass.taxonomy.loader import load_taxonomy

REPO_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = load_taxonomy(
    REPO_ROOT / "taxonomy" / "skills.yaml", REPO_ROOT / "taxonomy" / "roles.yaml"
)


class FakeMessage:
    def __init__(self, content: str | None):
        self.content = content


class FakeResponse:
    def __init__(self, content: str | None, done_reason: str = "stop"):
        self.message = FakeMessage(content)
        self.done_reason = done_reason


class FakeClient:
    """Stand-in for ollama.Client. Records every chat() call for inspection."""

    def __init__(
        self,
        content: str | None = None,
        raise_exc: Exception | None = None,
        done_reason: str = "stop",
    ):
        self._content = content
        self._raise_exc = raise_exc
        self._done_reason = done_reason
        self.calls: list[dict] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise_exc is not None:
            raise self._raise_exc
        return FakeResponse(self._content, done_reason=self._done_reason)


def _install_fake_client(monkeypatch, client: FakeClient) -> FakeClient:
    monkeypatch.setattr(ollama_llm, "_get_client", lambda host, timeout_seconds: client)
    return client


def test_schema_enum_matches_taxonomy_exactly():
    skill_ids = sorted(TAXONOMY.skills)
    schema = ollama_llm._build_schema(skill_ids)
    assert schema["properties"]["skills_present"]["items"]["enum"] == skill_ids


def test_prompt_contains_every_skill_id_and_resume_text():
    skill_ids = sorted(TAXONOMY.skills)
    resume_text = "UNIQUE_RESUME_MARKER built with Python and SQL."
    prompt = ollama_llm._build_prompt(skill_ids, resume_text, "rung3_v1")

    for skill_id in skill_ids:
        assert skill_id in prompt
    assert resume_text in prompt
    assert "RESUME:" in prompt


def test_valid_response_is_sorted_and_deduplicated(monkeypatch):
    content = json.dumps({"skills_present": ["sql", "python", "python"]})
    client = _install_fake_client(monkeypatch, FakeClient(content=content))

    result = ollama_llm.extract_skills("some resume text", TAXONOMY)

    assert result == sorted({"python", "sql"})
    assert len(client.calls) == 1


def test_malformed_json_raises_typed_error(monkeypatch):
    _install_fake_client(monkeypatch, FakeClient(content="not json"))

    with pytest.raises(ollama_llm.Rung3ExtractionError):
        ollama_llm.extract_skills("some resume text", TAXONOMY)


def test_missing_skills_present_key_raises_typed_error(monkeypatch):
    _install_fake_client(monkeypatch, FakeClient(content=json.dumps({"oops": []})))

    with pytest.raises(ollama_llm.Rung3ExtractionError):
        ollama_llm.extract_skills("some resume text", TAXONOMY)


def test_unknown_skill_id_raises_typed_error_naming_it(monkeypatch):
    content = json.dumps({"skills_present": ["python", "not_a_real_skill"]})
    _install_fake_client(monkeypatch, FakeClient(content=content))

    with pytest.raises(ollama_llm.Rung3ExtractionError, match="not_a_real_skill"):
        ollama_llm.extract_skills("some resume text", TAXONOMY)


def test_connection_error_raises_typed_error(monkeypatch):
    _install_fake_client(monkeypatch, FakeClient(raise_exc=ConnectionError("refused")))

    with pytest.raises(ollama_llm.Rung3ExtractionError):
        ollama_llm.extract_skills("some resume text", TAXONOMY)


def test_empty_model_response_is_not_swallowed_into_empty_list(monkeypatch):
    _install_fake_client(monkeypatch, FakeClient(content=None))

    with pytest.raises(ollama_llm.Rung3ExtractionError):
        ollama_llm.extract_skills("some resume text", TAXONOMY)


def test_model_override_takes_precedence_over_config(monkeypatch):
    monkeypatch.setattr(
        ollama_llm,
        "load_default_yaml",
        lambda: {"extract": {"rung3": {"model": "qwen3:8b"}}},
    )
    client = _install_fake_client(
        monkeypatch, FakeClient(content=json.dumps({"skills_present": []}))
    )

    ollama_llm.extract_skills("some resume text", TAXONOMY, model="phi4-mini")

    assert len(client.calls) == 1
    assert client.calls[0]["model"] == "phi4-mini"
    assert ollama_llm.resolved_model("phi4-mini") == "phi4-mini"


def test_resolved_model_falls_back_to_config(monkeypatch):
    monkeypatch.setattr(
        ollama_llm,
        "load_default_yaml",
        lambda: {"extract": {"rung3": {"model": "gemma4:e4b"}}},
    )
    assert ollama_llm.resolved_model(None) == "gemma4:e4b"


def test_config_values_are_passed_to_client(monkeypatch):
    monkeypatch.setattr(
        ollama_llm,
        "load_default_yaml",
        lambda: {
            "extract": {
                "rung3": {
                    "model": "phi4-mini",
                    "num_ctx": 4096,
                    "seed": 7,
                    "temperature": 0,
                }
            }
        },
    )
    client = _install_fake_client(
        monkeypatch, FakeClient(content=json.dumps({"skills_present": []}))
    )

    result = ollama_llm.extract_skills("some resume text", TAXONOMY)

    assert result == []
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == "phi4-mini"
    assert call["options"]["num_ctx"] == 4096
    assert call["options"]["seed"] == 7
    assert call["options"]["temperature"] == 0
    assert call["think"] is False


def test_num_predict_from_config_is_passed_to_client(monkeypatch):
    monkeypatch.setattr(
        ollama_llm,
        "load_default_yaml",
        lambda: {"extract": {"rung3": {"num_predict": 2048}}},
    )
    client = _install_fake_client(
        monkeypatch, FakeClient(content=json.dumps({"skills_present": []}))
    )

    ollama_llm.extract_skills("some resume text", TAXONOMY)

    assert len(client.calls) == 1
    assert client.calls[0]["options"]["num_predict"] == 2048


def test_done_reason_length_raises_typed_error_even_with_valid_json(monkeypatch):
    content = json.dumps({"skills_present": ["python"]})
    _install_fake_client(monkeypatch, FakeClient(content=content, done_reason="length"))

    with pytest.raises(ollama_llm.Rung3ExtractionError, match="num_predict cap") as exc_info:
        ollama_llm.extract_skills("some resume text", TAXONOMY)
    assert "qwen3:8b" in str(exc_info.value)


def test_done_reason_stop_with_valid_json_is_normal_result(monkeypatch):
    content = json.dumps({"skills_present": ["python", "sql"]})
    _install_fake_client(monkeypatch, FakeClient(content=content, done_reason="stop"))

    result = ollama_llm.extract_skills("some resume text", TAXONOMY)

    assert result == ["python", "sql"]
