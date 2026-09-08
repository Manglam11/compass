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

## Taxonomy

`taxonomy/skills.yaml` and `taxonomy/roles.yaml` define the skill/role
taxonomy: skills (id, display name, family, aliases) and roles (id, display
name, and their core/supporting/differentiator skill weights). Both files are
currently placeholders — real content lands in a later milestone.

The two files are versioned together: `roles.yaml`'s `taxonomy_version` field
is the version stamped on every recommendation Compass produces, and both
files' `version` fields must match it — `src/compass/taxonomy/loader.py`
cross-validates this along with alias uniqueness, id references, and weight
bucket consistency, collecting every violation into a single error instead of
stopping at the first one.

Validate the taxonomy files with:

```bash
uv run python scripts/validate_taxonomy.py
```

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

# Validate the taxonomy files
uv run python scripts/validate_taxonomy.py
```
