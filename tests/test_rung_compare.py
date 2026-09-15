"""Tests for scripts/rung_compare.py's rung-3 wiring: --rungs/--model
argument validation, the default-rungs code path, and the results payload.

No live Ollama server, resume files, or network calls: compass.eval.extraction
functions used by main() are monkeypatched directly on the rung_compare
module.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import rung_compare
from test_eval_agreement import S06_SHAPED_CANDIDATE

from compass.eval.agreement import compute_agreement
from compass.eval.extraction import Rung3Results


def test_default_rungs_is_1_and_2_with_no_model():
    args = rung_compare.parse_args(["--own-resume", "dummy.pdf"])
    assert args.rungs == ["1", "2"]
    assert args.model is None


def test_model_without_rung3_selected_is_a_clear_error(capsys):
    with pytest.raises(SystemExit):
        rung_compare.parse_args(["--own-resume", "dummy.pdf", "--model", "phi4-mini"])
    err = capsys.readouterr().err.lower()
    assert "--model" in err
    assert "rung 3" in err or "--rungs" in err


def test_model_with_rung3_selected_is_accepted():
    args = rung_compare.parse_args(
        ["--own-resume", "dummy.pdf", "--rungs", "3", "--model", "phi4-mini"]
    )
    assert args.rungs == ["3"]
    assert args.model == "phi4-mini"


def test_invalid_rung_value_is_a_clear_error(capsys):
    with pytest.raises(SystemExit):
        rung_compare.parse_args(["--own-resume", "dummy.pdf", "--rungs", "1,9"])
    assert "invalid" in capsys.readouterr().err.lower()


def test_default_flow_runs_rung1_and_rung2_only_never_touching_rung3(monkeypatch, capsys):
    def fake_load_resume_extractions(taxonomy, files_by_key):
        return dict(S06_SHAPED_CANDIDATE), dict(S06_SHAPED_CANDIDATE), {}

    def fail_if_called(*args, **kwargs):
        raise AssertionError("rung 3 must not run unless --rungs includes 3")

    monkeypatch.setattr(rung_compare, "load_taxonomy", lambda *a, **k: None)
    monkeypatch.setattr(rung_compare, "load_resume_extractions", fake_load_resume_extractions)
    monkeypatch.setattr(rung_compare, "run_rung3", fail_if_called)
    monkeypatch.setattr(rung_compare, "load_resume_texts", fail_if_called)

    exit_code = rung_compare.main(["--own-resume", "dummy.pdf"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "rung 1 (gazetteer) vs reference:" in out
    assert "rung 2 (embeddings) vs reference:" in out
    assert "rung 3" not in out
    assert "total_candidate=61" in out
    assert "total_agreed=51" in out


def test_results_payload_has_required_keys_and_no_resume_text():
    rung3_result = Rung3Results(
        skills_by_resume={"prac_001": {"python", "sql"}},
        seconds_by_resume={"prac_001": 1.5},
        failures={"prac_006": "Ollama returned an empty response"},
        warmup_seconds=3.2,
    )
    _, aggregate = compute_agreement(
        {"prac_001": {"python", "sql"}}, {"prac_001": {"python", "sql"}}
    )

    payload = rung_compare.build_results_payload(
        model="qwen3:8b",
        prompt_version="rung3_v1",
        taxonomy_version="v1",
        ollama_package_version="0.6.2",
        ollama_server_version="0.5.1",
        rung3_result=rung3_result,
        aggregate=aggregate,
    )

    assert set(payload.keys()) == {
        "timestamp",
        "model",
        "prompt_version",
        "taxonomy_version",
        "ollama_package_version",
        "ollama_server_version",
        "warmup_seconds",
        "per_resume",
        "failures",
        "aggregate",
    }
    assert payload["per_resume"] == {"prac_001": {"skills": ["python", "sql"], "seconds": 1.5}}
    assert payload["failures"] == {"prac_006": "Ollama returned an empty response"}
    assert payload["aggregate"]["total_candidate"] == 2

    # Round-trips through JSON (what write_results_file actually writes).
    json.dumps(payload)


def test_write_results_file_writes_json_named_by_model(tmp_path):
    payload = {"model": "qwen3:8b", "hello": "world"}
    path = rung_compare.write_results_file(payload, results_dir=tmp_path)

    assert path.exists()
    assert path.parent == tmp_path
    assert "qwen3-8b" in path.name
    assert json.loads(path.read_text(encoding="utf-8")) == payload
