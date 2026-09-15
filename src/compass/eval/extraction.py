"""Shared resume-loading + rung extraction, used by scripts/rung_compare.py
and scripts/rung_grounding.py so scripts can't drift on how resumes are
loaded and extracted.

load_resume_extractions() is the original rung-1/rung-2-only helper, kept
exactly as-is since scripts/rung_grounding.py depends on its 3-tuple return.
load_resume_texts() and run_rung3() are the newer, selectable pieces used by
scripts/rung_compare.py's --rungs flag to add rung 3 (a local LLM via
Ollama): they support per-resume timing, an untimed warm-up call, and
per-resume failure tracking. A rung 3 failure on a resume is recorded and
that resume is excluded from agreement totals -- it is never folded in as an
empty skill list.
"""

from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from compass.extract import embeddings, gazetteer, ollama_llm
from compass.extract.ollama_llm import Rung3ExtractionError
from compass.resume_intake.text import extract_resume_text
from compass.taxonomy.models import Taxonomy


def load_resume_extractions(
    taxonomy: Taxonomy,
    files_by_key: dict[str, Path],
) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, str]]:
    rung1_by_key: dict[str, set[str]] = {}
    rung2_by_key: dict[str, set[str]] = {}
    text_by_key: dict[str, str] = {}

    for key, path in files_by_key.items():
        try:
            text = extract_resume_text(path)
            rung1_by_key[key] = set(gazetteer.extract_skills(text, taxonomy))
            rung2_by_key[key] = set(embeddings.extract_skills(text, taxonomy))
            text_by_key[key] = text
        except Exception as exc:
            raise RuntimeError(f"failed to extract resume {key!r} ({path}): {exc}") from exc

    return rung1_by_key, rung2_by_key, text_by_key


def load_resume_texts(files_by_key: dict[str, Path]) -> dict[str, str]:
    """Resume text only, no rung 1/2 extraction -- for a rung-3-only run."""
    text_by_key: dict[str, str] = {}
    for key, path in files_by_key.items():
        try:
            text_by_key[key] = extract_resume_text(path)
        except Exception as exc:
            raise RuntimeError(f"failed to extract resume {key!r} ({path}): {exc}") from exc
    return text_by_key


@dataclass
class Rung3Results:
    skills_by_resume: dict[str, set[str]]
    seconds_by_resume: dict[str, float]
    failures: dict[str, str]
    warmup_seconds: float


def run_rung3(
    taxonomy: Taxonomy,
    texts_by_key: dict[str, str],
    model: str | None = None,
) -> Rung3Results:
    # Untimed warm-up: loads the model into VRAM so resume #1's timed call
    # doesn't pay for that load. Not wrapped in try/except -- if the server
    # is unreachable, every timed call below would fail identically, so
    # failing fast here with a clear traceback is more useful than 6
    # individually-recorded, identical failures.
    warmup_start = time.perf_counter()
    ollama_llm.extract_skills(
        "Warm-up call to load the model into memory before timed extraction.",
        taxonomy,
        model=model,
    )
    warmup_seconds = time.perf_counter() - warmup_start

    skills_by_resume: dict[str, set[str]] = {}
    seconds_by_resume: dict[str, float] = {}
    failures: dict[str, str] = {}

    for key, text in texts_by_key.items():
        start = time.perf_counter()
        try:
            skills = ollama_llm.extract_skills(text, taxonomy, model=model)
        except Rung3ExtractionError as exc:
            seconds_by_resume[key] = time.perf_counter() - start
            failures[key] = str(exc)
            continue
        seconds_by_resume[key] = time.perf_counter() - start
        skills_by_resume[key] = set(skills)

    return Rung3Results(
        skills_by_resume=skills_by_resume,
        seconds_by_resume=seconds_by_resume,
        failures=failures,
        warmup_seconds=warmup_seconds,
    )


def latency_summary(
    seconds_by_resume: dict[str, float], failures: dict[str, str] | None = None
) -> tuple[float, float]:
    """(median, max) of per-resume seconds for successful calls only -- a
    timed-out failure (e.g. a repetition loop that ran to the timeout) must
    not distort these numbers. (0.0, 0.0) if there are no successful calls.
    """
    failed_keys = set(failures) if failures else set()
    values = [seconds for key, seconds in seconds_by_resume.items() if key not in failed_keys]
    if not values:
        return 0.0, 0.0
    return statistics.median(values), max(values)


def failed_seconds(
    seconds_by_resume: dict[str, float], failures: dict[str, str]
) -> dict[str, float]:
    """Per-resume seconds for failed calls only, reported separately from
    latency_summary so a timeout doesn't hide inside median/max.
    """
    return {key: seconds_by_resume[key] for key in failures}


def get_server_version(host: str, timeout_seconds: float = 5.0) -> str | None:
    """The Ollama server's reported version, or None if it can't be reached."""
    url = host.rstrip("/") + "/api/version"
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    return payload.get("version")
