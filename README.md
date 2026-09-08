# Compass

Compass takes a resume file (PDF or DOCX), extracts skills from it, and matches
those skills against a role taxonomy to surface which roles a candidate is a
fit for — and which roles were excluded, and why. This repo currently holds
only the frozen v1 API contract and project scaffolding; extraction, matching,
and taxonomy content are built in later milestones.

## Repo map

- `src/compass/contracts/v1.py` — the v1 request/response contract (pydantic
  v2 models). This is the single source of truth for the API shape.
- `contracts/v1/*.schema.json` — JSON Schema, generated from `v1.py`. Never
  hand-edit these; regenerate with `scripts/export_schema.py`.
- `contracts/v1/examples/` — example request/response/error payloads used by
  the contract tests.
- `src/compass/config.py` — settings loading (pydantic-settings + non-secret
  YAML defaults).
- `config/default.yaml` — non-secret default configuration.
- `.env.example` — names of environment variables Compass reads; copy to
  `.env` and fill in locally, never commit `.env`.
- `taxonomy/`, `data/golden/`, `eval/` — placeholders for future milestones.
- `scripts/export_schema.py` — generates JSON Schema from the contract models.
- `tests/test_contract_v1.py` — contract tests, loaded from the example JSON
  files.

## Commands

All commands run through `uv` — no pip, no manually activated virtualenvs.

```bash
# Run the test suite
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Regenerate contracts/v1/*.schema.json from the pydantic models
uv run python scripts/export_schema.py
```
