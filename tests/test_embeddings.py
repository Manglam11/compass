"""Tests for compass.extract.embeddings.

Uses a deterministic, dependency-free fake in place of the real
SentenceTransformer model so the suite never downloads weights and runs in
milliseconds.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from compass.extract import embeddings
from compass.taxonomy.loader import load_taxonomy

REPO_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY = load_taxonomy(
    REPO_ROOT / "taxonomy" / "skills.yaml", REPO_ROOT / "taxonomy" / "roles.yaml"
)

DIM = 256


def _hash_vector(text: str) -> np.ndarray:
    """Deterministic pseudo-random vector, stable across processes."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big")
    rng = np.random.default_rng(seed)
    return rng.normal(size=DIM)


class FakeModel:
    """Stand-in for SentenceTransformer.

    Every text hashes to a fixed pseudo-random vector, so unrelated texts
    are (with overwhelming probability, at DIM=256) far below any realistic
    threshold. `aligned` texts are pinned to an identical vector so a
    specific span/description pair can be forced to match.
    """

    def __init__(self, aligned: tuple[str, ...] = ()):
        self._aligned_vector = np.ones(DIM)
        self._aligned = set(aligned)

    def encode(self, texts: list[str]) -> np.ndarray:
        return np.array(
            [
                self._aligned_vector if text in self._aligned else _hash_vector(text)
                for text in texts
            ]
        )


@pytest.fixture(autouse=True)
def _reset_caches_and_model(monkeypatch):
    embeddings.clear_caches()
    monkeypatch.setattr(embeddings, "_get_model", lambda: FakeModel())
    yield
    embeddings.clear_caches()


def test_extraction_is_closed_vocabulary():
    result = embeddings.extract_skills(
        "This resume mentions nothing that lines up with any skill.", TAXONOMY
    )
    assert set(result) <= set(TAXONOMY.skills)


def test_same_input_twice_gives_same_output():
    text = "Wrote Python scripts and managed PostgreSQL databases for reporting."
    first = embeddings.extract_skills(text, TAXONOMY)
    second = embeddings.extract_skills(text, TAXONOMY)
    assert first == second


def test_result_is_sorted_and_deduplicated():
    text = "Some resume line that is long enough to count as a span here."
    result = embeddings.extract_skills(text, TAXONOMY)
    assert result == sorted(set(result))


def test_span_above_threshold_extracts_its_skill(monkeypatch):
    python_description = TAXONOMY.skills["python"].description
    span_text = "A resume line engineered to align with the python description."

    monkeypatch.setattr(
        embeddings, "_get_model", lambda: FakeModel(aligned=(python_description, span_text))
    )

    text = f"Irrelevant short-dropped filler.\n{span_text}"
    result = embeddings.extract_skills(text, TAXONOMY)

    assert "python" in result


def test_threshold_is_read_from_config_not_hardcoded(monkeypatch):
    python_description = TAXONOMY.skills["python"].description
    span_text = "A resume line engineered to align with the python description."

    monkeypatch.setattr(
        embeddings, "_get_model", lambda: FakeModel(aligned=(python_description, span_text))
    )
    text = f"Irrelevant short-dropped filler.\n{span_text}"

    monkeypatch.setattr(embeddings, "load_default_yaml", lambda: {"extract": {}})
    assert "python" in embeddings.extract_skills(text, TAXONOMY)

    monkeypatch.setattr(
        embeddings, "load_default_yaml", lambda: {"extract": {"embedding_threshold": 1.1}}
    )
    assert "python" not in embeddings.extract_skills(text, TAXONOMY)


def test_no_spans_returns_no_skills():
    assert embeddings.extract_skills("short\ntiny", TAXONOMY) == []
