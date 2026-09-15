"""Extract taxonomy skill ids from resume text via a local LLM served by Ollama.

Rung 3 of the extraction ladder: a local open-weight model (configurable via
config/default.yaml, default qwen3:8b) constrained to the taxonomy's closed
vocabulary through structured output — a JSON schema whose enum is exactly
the taxonomy skill ids, passed to Ollama as `format`. Sits behind the same
interface as compass.extract.gazetteer and compass.extract.embeddings so all
three rungs are interchangeable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import ollama

from compass.config import load_default_yaml
from compass.taxonomy.models import Taxonomy

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

DEFAULTS: dict[str, Any] = {
    "model": "qwen3:8b",
    "host": "http://127.0.0.1:11434",
    "timeout_seconds": 300,
    "num_ctx": 8192,
    "temperature": 0,
    "seed": 42,
    "prompt_version": "rung3_v1",
}


class Rung3ExtractionError(Exception):
    """Raised when the Ollama rung fails to produce a valid closed-vocabulary result."""


def rung3_config() -> dict[str, Any]:
    config = load_default_yaml()
    return {**DEFAULTS, **config.get("extract", {}).get("rung3", {})}


def _get_client(host: str, timeout_seconds: float) -> ollama.Client:
    return ollama.Client(host=host, timeout=timeout_seconds)


def _load_prompt_template(prompt_version: str) -> str:
    path = PROMPTS_DIR / f"{prompt_version}.txt"
    if not path.exists():
        raise Rung3ExtractionError(f"unknown prompt_version {prompt_version!r}: {path} not found")
    return path.read_text(encoding="utf-8")


def _build_prompt(skill_ids: list[str], resume_text: str, prompt_version: str) -> str:
    template = _load_prompt_template(prompt_version)
    # .replace(), not .format(): the prompt's JSON example already contains
    # literal { } that str.format would misparse as replacement fields.
    rules = template.replace("{N}", str(len(skill_ids))).replace(
        "{SKILL_LIST}", "\n".join(skill_ids)
    )
    return f"{rules}\nRESUME:\n{resume_text}"


def _build_schema(skill_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "skills_present": {
                "type": "array",
                "items": {"type": "string", "enum": skill_ids},
            }
        },
        "required": ["skills_present"],
    }


def resolved_model(model: str | None = None) -> str:
    """The model name that a call to extract_skills will actually use."""
    return model if model is not None else rung3_config()["model"]


def extract_skills(text: str, taxonomy: Taxonomy, *, model: str | None = None) -> list[str]:
    config = rung3_config()
    effective_model = model if model is not None else config["model"]
    skill_ids = sorted(taxonomy.skills)

    prompt = _build_prompt(skill_ids, text, config["prompt_version"])
    schema = _build_schema(skill_ids)
    client = _get_client(config["host"], config["timeout_seconds"])

    try:
        response = client.chat(
            model=effective_model,
            messages=[{"role": "user", "content": prompt}],
            format=schema,
            options={
                "temperature": config["temperature"],
                "seed": config["seed"],
                "num_ctx": config["num_ctx"],
            },
            think=False,
        )
    except Exception as exc:
        raise Rung3ExtractionError(
            f"Ollama request to model {effective_model!r} at {config['host']} failed "
            f"(server not running, or timed out after {config['timeout_seconds']}s): {exc}"
        ) from exc

    content = response.message.content
    if not content:
        raise Rung3ExtractionError("Ollama returned an empty response")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise Rung3ExtractionError(f"Ollama response was not valid JSON: {content!r}") from exc

    if not isinstance(parsed, dict) or "skills_present" not in parsed:
        raise Rung3ExtractionError(f"Ollama response missing 'skills_present' key: {parsed!r}")

    skills_present = parsed["skills_present"]
    if not isinstance(skills_present, list):
        raise Rung3ExtractionError(
            f"Ollama response 'skills_present' was not a list: {skills_present!r}"
        )

    valid_ids = set(taxonomy.skills)
    unknown = sorted({skill_id for skill_id in skills_present if skill_id not in valid_ids})
    if unknown:
        raise Rung3ExtractionError(
            f"Ollama returned skill id(s) outside the taxonomy: {', '.join(unknown)}"
        )

    return sorted(set(skills_present))
