"""Runs a single alias-mining batch through the local Ollama model.

Mirrors compass.extract.ollama_llm's conventions (structured `format` schema
constrained to a closed vocabulary, temperature/seed/num_ctx/think settings,
the done_reason == "length" check before any JSON parsing, a single named
error type instead of a silently empty result) but for the mining prompt
built by compass.mining.prompt_builder: a list of proposals per batch rather
than a single skills_present list, and a vocabulary of the taxonomy's 59
skill ids plus the literal "NEW" for an unmapped skill.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from compass.extract.ollama_llm import DEFAULTS as RUNG3_DEFAULTS
from compass.mining.corpus_loader import CorpusResume
from compass.mining.prompt_builder import build_mining_prompt
from compass.taxonomy.models import Taxonomy

# Mining batches are much larger prompts than rung 3 single-resume extraction
# and the response is a list of proposals rather than one skills_present
# array, so it needs far more headroom than rung3's 1024 cap.
NUM_PREDICT = 4096

_REQUIRED_KEYS = ("resume_id", "skill_id", "quoted_phrase")


class MiningBatchError(Exception):
    """Raised when a mining batch fails to produce a valid list of proposals."""


@dataclass
class ProposalRecord:
    resume_id: str
    skill_id: str
    quoted_phrase: str
    model: str
    batch_index: int
    suggested_name: str | None = None


def _build_schema(skill_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "resume_id": {"type": "string"},
                "skill_id": {"type": "string", "enum": [*skill_ids, "NEW"]},
                "quoted_phrase": {"type": "string"},
                "suggested_name": {"type": "string"},
            },
            "required": list(_REQUIRED_KEYS),
        },
    }


def run_mining_batch(
    batch: list[CorpusResume],
    taxonomy: Taxonomy,
    model: str,
    client: Any,
    *,
    batch_index: int = 0,
) -> list[ProposalRecord]:
    skill_ids = sorted(taxonomy.skills)
    valid_ids = set(skill_ids) | {"NEW"}

    prompt = build_mining_prompt(batch, taxonomy)
    schema = _build_schema(skill_ids)

    try:
        response = client.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            format=schema,
            options={
                "temperature": RUNG3_DEFAULTS["temperature"],
                "seed": RUNG3_DEFAULTS["seed"],
                "num_ctx": RUNG3_DEFAULTS["num_ctx"],
                "num_predict": NUM_PREDICT,
            },
            think=False,
        )
    except Exception as exc:
        raise MiningBatchError(
            f"Ollama request to model {model!r} failed (server not running, or timed "
            f"out after {RUNG3_DEFAULTS['timeout_seconds']}s): {exc}"
        ) from exc

    if response.done_reason == "length":
        raise MiningBatchError(
            f"Ollama model {model!r} output hit num_predict cap on batch {batch_index} "
            f"(probable repetition loop or an oversized batch)"
        )

    content = response.message.content
    if not content:
        raise MiningBatchError(f"Ollama model {model!r} returned an empty response")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise MiningBatchError(f"Ollama response was not valid JSON: {content!r}") from exc

    if not isinstance(parsed, list):
        raise MiningBatchError(f"Ollama response was not a JSON list: {parsed!r}")

    records: list[ProposalRecord] = []
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise MiningBatchError(f"proposal[{i}] was not a JSON object: {item!r}")

        missing = [key for key in _REQUIRED_KEYS if key not in item]
        if missing:
            raise MiningBatchError(f"proposal[{i}] missing required key(s) {missing}: {item!r}")

        skill_id = item["skill_id"]
        if skill_id not in valid_ids:
            raise MiningBatchError(
                f"proposal[{i}] has skill_id {skill_id!r}, outside the taxonomy's "
                f'{len(skill_ids)} ids plus "NEW"'
            )

        records.append(
            ProposalRecord(
                resume_id=item["resume_id"],
                skill_id=skill_id,
                quoted_phrase=item["quoted_phrase"],
                model=model,
                batch_index=batch_index,
                suggested_name=item.get("suggested_name") if skill_id == "NEW" else None,
            )
        )

    return records
