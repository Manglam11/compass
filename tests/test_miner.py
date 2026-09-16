"""Tests for compass.mining.miner.

The Ollama client is fully mocked: no live model, no network, no Docker in
this suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from compass.mining import miner
from compass.mining.corpus_loader import CorpusResume
from compass.taxonomy.loader import load_taxonomy

REPO_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = load_taxonomy(
    REPO_ROOT / "taxonomy" / "skills.yaml", REPO_ROOT / "taxonomy" / "roles.yaml"
)

BATCH = [
    CorpusResume(resume_id="0000", category="Data Science", text="Built pipelines in Py."),
    CorpusResume(resume_id="0001", category="Data Science", text="Used Snowflake warehouse."),
]


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


def test_schema_enum_is_taxonomy_ids_plus_new():
    skill_ids = sorted(TAXONOMY.skills)
    schema = miner._build_schema(skill_ids)
    assert schema["items"]["properties"]["skill_id"]["enum"] == [*skill_ids, "NEW"]


def test_successful_batch_parses_into_proposal_records():
    content = json.dumps(
        [
            {"resume_id": "0000", "skill_id": "python", "quoted_phrase": "Py"},
            {
                "resume_id": "0001",
                "skill_id": "NEW",
                "quoted_phrase": "Snowflake",
                "suggested_name": "snowflake",
            },
        ]
    )
    client = FakeClient(content=content)

    records = miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client, batch_index=3)

    assert len(records) == 2
    assert records[0] == miner.ProposalRecord(
        resume_id="0000",
        skill_id="python",
        quoted_phrase="Py",
        model="qwen3:8b",
        batch_index=3,
        suggested_name=None,
    )
    assert records[1] == miner.ProposalRecord(
        resume_id="0001",
        skill_id="NEW",
        quoted_phrase="Snowflake",
        model="qwen3:8b",
        batch_index=3,
        suggested_name="snowflake",
    )
    assert len(client.calls) == 1


def test_empty_list_is_a_valid_result():
    client = FakeClient(content=json.dumps([]))

    records = miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client)

    assert records == []


def test_malformed_json_raises_mining_batch_error():
    client = FakeClient(content="not json")

    with pytest.raises(miner.MiningBatchError):
        miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client)


def test_response_not_a_list_raises_mining_batch_error():
    client = FakeClient(content=json.dumps({"oops": []}))

    with pytest.raises(miner.MiningBatchError):
        miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client)


def test_missing_required_key_raises_mining_batch_error():
    content = json.dumps([{"resume_id": "0000", "skill_id": "python"}])
    client = FakeClient(content=content)

    with pytest.raises(miner.MiningBatchError, match="quoted_phrase"):
        miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client)


def test_unknown_skill_id_raises_mining_batch_error_naming_it():
    content = json.dumps(
        [{"resume_id": "0000", "skill_id": "not_a_real_skill", "quoted_phrase": "Py"}]
    )
    client = FakeClient(content=content)

    with pytest.raises(miner.MiningBatchError, match="not_a_real_skill"):
        miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client)


def test_connection_error_raises_mining_batch_error():
    client = FakeClient(raise_exc=ConnectionError("refused"))

    with pytest.raises(miner.MiningBatchError):
        miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client)


def test_timeout_error_raises_mining_batch_error():
    client = FakeClient(raise_exc=TimeoutError("timed out"))

    with pytest.raises(miner.MiningBatchError):
        miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client)


def test_done_reason_length_raises_before_parsing_even_with_valid_json():
    content = json.dumps([{"resume_id": "0000", "skill_id": "python", "quoted_phrase": "Py"}])
    client = FakeClient(content=content, done_reason="length")

    with pytest.raises(miner.MiningBatchError, match="num_predict cap"):
        miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client)


def test_empty_content_raises_mining_batch_error():
    client = FakeClient(content=None)

    with pytest.raises(miner.MiningBatchError):
        miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client)


def test_num_predict_and_options_passed_to_client():
    client = FakeClient(content=json.dumps([]))

    miner.run_mining_batch(BATCH, TAXONOMY, "qwen3:8b", client)

    call = client.calls[0]
    assert call["options"]["num_predict"] == miner.NUM_PREDICT
    assert call["options"]["temperature"] == 0
    assert call["options"]["seed"] == 42
    assert call["options"]["num_ctx"] == 8192
    assert call["think"] is False
