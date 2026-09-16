"""Tests for scripts/mine_aliases.py.

The Ollama client and corpus loading are fully mocked/monkeypatched: no live
model, no network, no real corpus file read in this suite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import mine_aliases

from compass.mining.miner import MiningBatchError, ProposalRecord


def test_append_records_writes_new_file(tmp_path):
    output_path = tmp_path / "proposals_raw.json"
    records = [
        ProposalRecord(
            resume_id="0000",
            skill_id="python",
            quoted_phrase="Py",
            model="qwen3:8b",
            batch_index=0,
        )
    ]

    mine_aliases.append_records(output_path, records)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data == [
        {
            "resume_id": "0000",
            "skill_id": "python",
            "quoted_phrase": "Py",
            "model": "qwen3:8b",
            "batch_index": 0,
        }
    ]


def test_append_records_omits_suggested_name_when_none(tmp_path):
    output_path = tmp_path / "proposals_raw.json"
    records = [
        ProposalRecord(
            resume_id="0001",
            skill_id="NEW",
            quoted_phrase="Snowflake",
            model="qwen3:8b",
            batch_index=0,
            suggested_name="snowflake",
        )
    ]

    mine_aliases.append_records(output_path, records)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data[0]["suggested_name"] == "snowflake"

    output_path2 = tmp_path / "proposals_raw2.json"
    mine_aliases.append_records(
        output_path2,
        [
            ProposalRecord(
                resume_id="0002",
                skill_id="python",
                quoted_phrase="Py",
                model="qwen3:8b",
                batch_index=0,
            )
        ],
    )
    data2 = json.loads(output_path2.read_text(encoding="utf-8"))
    assert "suggested_name" not in data2[0]


def test_append_records_accumulates_across_calls(tmp_path):
    output_path = tmp_path / "proposals_raw.json"
    first = [
        ProposalRecord(
            resume_id="0000", skill_id="python", quoted_phrase="Py", model="m", batch_index=0
        )
    ]
    second = [
        ProposalRecord(
            resume_id="0001", skill_id="sql", quoted_phrase="SQL", model="m", batch_index=1
        )
    ]

    mine_aliases.append_records(output_path, first)
    mine_aliases.append_records(output_path, second)

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["skill_id"] == "python"
    assert data[1]["skill_id"] == "sql"


def test_batch_failure_is_logged_and_run_continues(tmp_path, monkeypatch, capsys):
    """Simulates a mid-run failure: the second of three batches raises
    MiningBatchError. The first batch's output must survive on disk, and the
    third batch must still run.
    """
    output_path = tmp_path / "proposals_raw.json"

    resumes = [f"resume-{i}" for i in range(3)]  # stand in for CorpusResume batches
    batches = [[r] for r in resumes]

    monkeypatch.setattr(mine_aliases, "load_corpus", lambda path: (resumes, 0))
    monkeypatch.setattr(mine_aliases, "batch_resumes", lambda resumes, char_budget: batches)
    monkeypatch.setattr(mine_aliases.ollama, "Client", lambda host, timeout: object())
    monkeypatch.setattr(mine_aliases, "load_taxonomy", lambda skills_path, roles_path: object())

    call_count = {"n": 0}

    def fake_run_mining_batch(batch, taxonomy, model, client, *, batch_index):
        call_count["n"] += 1
        if batch_index == 1:
            raise MiningBatchError("boom on batch 1")
        return [
            ProposalRecord(
                resume_id=f"r{batch_index}",
                skill_id="python",
                quoted_phrase="Py",
                model=model,
                batch_index=batch_index,
            )
        ]

    monkeypatch.setattr(mine_aliases, "run_mining_batch", fake_run_mining_batch)

    exit_code = mine_aliases.main(["--model", "gemma4:e4b", "--output", str(output_path)])

    assert exit_code == 1
    assert call_count["n"] == 3

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert [d["batch_index"] for d in data] == [0, 2]

    out = capsys.readouterr().out
    assert "FAILED" in out
    assert "boom on batch 1" in out

    manifest_path = tmp_path / "proposals_raw.manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["batches_total"] == 3
    assert manifest["batches_ok"] == 2
    assert manifest["batches_failed"] == 1
    assert manifest["proposals_count"] == 2
    assert manifest["model"] == "gemma4:e4b"
    assert [f["batch_index"] for f in manifest["failures"]] == [1]
    assert manifest["failures"][0]["error_type"] == "MiningBatchError"
    assert "boom on batch 1" in manifest["failures"][0]["message"]


def test_manifest_written_when_all_batches_fail(tmp_path, monkeypatch):
    """All batches fail: no proposals are ever appended, but the manifest and
    an empty proposals file must still exist -- a fully failed run must not
    look like a run that never happened.
    """
    output_path = tmp_path / "proposals_raw.json"

    resumes = [f"resume-{i}" for i in range(2)]
    batches = [[r] for r in resumes]

    monkeypatch.setattr(mine_aliases, "load_corpus", lambda path: (resumes, 1))
    monkeypatch.setattr(mine_aliases, "batch_resumes", lambda resumes, char_budget: batches)
    monkeypatch.setattr(mine_aliases.ollama, "Client", lambda host, timeout: object())
    monkeypatch.setattr(mine_aliases, "load_taxonomy", lambda skills_path, roles_path: object())

    def fake_run_mining_batch(batch, taxonomy, model, client, *, batch_index):
        raise MiningBatchError(f"boom on batch {batch_index}")

    monkeypatch.setattr(mine_aliases, "run_mining_batch", fake_run_mining_batch)

    exit_code = mine_aliases.main(["--model", "gemma4:e4b", "--output", str(output_path)])

    assert exit_code == 1

    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8")) == []

    manifest_path = tmp_path / "proposals_raw.manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["batches_total"] == 2
    assert manifest["batches_ok"] == 0
    assert manifest["batches_failed"] == 2
    assert manifest["proposals_count"] == 0
    assert manifest["model"] == "gemma4:e4b"
    assert [f["batch_index"] for f in manifest["failures"]] == [0, 1]
    assert all(f["error_type"] == "MiningBatchError" for f in manifest["failures"])
    assert manifest["corpus"] == {"rows_total": 3, "rows_unique_after_dedup": 2}
    assert manifest["config"]["char_budget"] == mine_aliases.CHAR_BUDGET
    assert manifest["config"]["num_predict"] == mine_aliases.NUM_PREDICT
    assert manifest["started_at"] <= manifest["finished_at"]
    assert "git_head" in manifest


def test_manifest_all_batches_succeed(tmp_path, monkeypatch):
    output_path = tmp_path / "proposals_raw.json"

    resumes = [f"resume-{i}" for i in range(2)]
    batches = [[r] for r in resumes]

    monkeypatch.setattr(mine_aliases, "load_corpus", lambda path: (resumes, 0))
    monkeypatch.setattr(mine_aliases, "batch_resumes", lambda resumes, char_budget: batches)
    monkeypatch.setattr(mine_aliases.ollama, "Client", lambda host, timeout: object())
    monkeypatch.setattr(mine_aliases, "load_taxonomy", lambda skills_path, roles_path: object())

    def fake_run_mining_batch(batch, taxonomy, model, client, *, batch_index):
        return [
            ProposalRecord(
                resume_id=f"r{batch_index}",
                skill_id="python",
                quoted_phrase="Py",
                model=model,
                batch_index=batch_index,
            )
        ]

    monkeypatch.setattr(mine_aliases, "run_mining_batch", fake_run_mining_batch)

    exit_code = mine_aliases.main(["--model", "gemma4:e4b", "--output", str(output_path)])

    assert exit_code == 0

    manifest_path = tmp_path / "proposals_raw.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["batches_total"] == 2
    assert manifest["batches_ok"] == 2
    assert manifest["batches_failed"] == 0
    assert manifest["failures"] == []
    assert manifest["proposals_count"] == 2
