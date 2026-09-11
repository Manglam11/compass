"""Extract taxonomy skill ids from resume text via embedding similarity.

Closed-vocabulary: a skill_id is only ever drawn from the taxonomy, never
invented from resume text. Each skill's `description` is embedded once and
cached in a single NumPy matrix; resume text is split into line-level spans
(see spans.py), each span is embedded, and a skill is extracted if any span
scores above the configured cosine-similarity threshold against it.

Sits behind the same interface as compass.extract.gazetteer.extract_skills
so the two rungs are interchangeable.
"""

from __future__ import annotations

import numpy as np

from compass.config import load_default_yaml
from compass.extract.spans import split_into_spans
from compass.taxonomy.models import Taxonomy

MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_THRESHOLD = 0.55

_model_cache: object | None = None
_skill_matrix_cache: dict[str, tuple[list[str], np.ndarray]] = {}


def clear_caches() -> None:
    """Drop the cached model and skill-embedding matrix. For tests only."""
    global _model_cache
    _model_cache = None
    _skill_matrix_cache.clear()


def _get_model() -> object:
    global _model_cache
    if _model_cache is None:
        from sentence_transformers import SentenceTransformer

        _model_cache = SentenceTransformer(MODEL_NAME)
    return _model_cache


def _threshold() -> float:
    config = load_default_yaml()
    return float(config.get("extract", {}).get("embedding_threshold", DEFAULT_THRESHOLD))


def _encode_normalized(model: object, texts: list[str], dim_hint: int = 0) -> np.ndarray:
    if not texts:
        return np.zeros((0, dim_hint))
    vectors = np.asarray(model.encode(texts), dtype=np.float64)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def _skill_matrix(taxonomy: Taxonomy, model: object) -> tuple[list[str], np.ndarray]:
    cached = _skill_matrix_cache.get(taxonomy.taxonomy_version)
    if cached is not None:
        return cached

    skill_ids = sorted(taxonomy.skills)
    descriptions = [taxonomy.skills[skill_id].description or "" for skill_id in skill_ids]
    matrix = _encode_normalized(model, descriptions)

    result = (skill_ids, matrix)
    _skill_matrix_cache[taxonomy.taxonomy_version] = result
    return result


def extract_skills(text: str, taxonomy: Taxonomy) -> list[str]:
    spans = split_into_spans(text)
    if not spans:
        return []

    model = _get_model()
    skill_ids, skill_matrix = _skill_matrix(taxonomy, model)
    span_matrix = _encode_normalized(model, spans, dim_hint=skill_matrix.shape[1])

    similarities = span_matrix @ skill_matrix.T  # (num_spans, num_skills)
    best_per_skill = similarities.max(axis=0)

    threshold = _threshold()
    found = {skill_ids[i] for i, score in enumerate(best_per_skill) if score > threshold}
    return sorted(found)
