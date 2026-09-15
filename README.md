# Compass

## What Compass does

Compass takes a candidate's resume (PDF or DOCX), extracts the technical
skills it can find, and matches those skills against a hand-built role
taxonomy to surface which roles the candidate is a fit for — including
roles the candidate didn't apply for. For example, a candidate who
self-identifies as a "Data Analyst" but whose resume shows scikit-learn,
feature engineering, and model evaluation work may also score as a fit
for Data Scientist or ML Engineer; Compass surfaces that even though the
candidate never used those words. Scoring is deterministic and rule-based
throughout — an LLM, where used, may phrase an explanation, but it never
decides a score.

## Architecture

- **Two-stage gate + score.** Each role has a core-skill gate: fail it
  (missing too many core skills) and the role is excluded outright,
  regardless of other overlap. Roles that pass the gate are then scored
  by weighted coverage across core/supporting/differentiator skill
  buckets.
- **Taxonomy in Git.** `taxonomy/skills.yaml` and `taxonomy/roles.yaml`
  are hand-authored, versioned files reviewed like code, not a database
  table — taxonomy changes are auditable via git history and covered by
  loader validation (`src/compass/taxonomy/loader.py`).
- **Deterministic scoring.** Given the same resume text, taxonomy
  version, and config, Compass always produces the same skill list and
  role scores — no sampling, no LLM in the scoring path.

## Extraction ladder status

| Rung | Approach | Status |
|---|---|---|
| 1 | spaCy gazetteer + alias list | **Shipped.** Zero cost, deterministic. |
| 2 | sentence-transformers embeddings (Qwen3-Embedding-0.6B), argmax per text-line span | **Built, rejected.** Config-switchable, stays in the codebase. Over-predicts on sparse resumes and under-predicts on dense ones because argmax forces every line to name some skill — output count tracks line count, not skill content. |
| 3 | Local open-weight LLM (candidates: Qwen3, Gemma 3 12B, Phi-4-mini, Mistral Small 3.1) | **Not started.** |
| 4 | Cloud API (Claude/GPT/Gemini) as a production extraction rung | **Not started as live code.** A cloud model (Claude Opus) was used manually, outside this repo, as a reference model for evaluation (see below) — that is not the same as a coded rung 4. |

Measured agreement numbers (from `scripts/rung_compare.py`, reproducible,
across 6 varied resumes — directional, not statistical, given the sample
size):

| Rung | Found | Reference | Agreed | Precision-analogue | Recall-analogue | Micro-Jaccard |
|---|---|---|---|---|---|---|
| 1 (gazetteer) | 61 | 64 | 51 | 84% | 80% | 0.69 |
| 2 (embeddings) | 98 | 64 | 32 | 33% | 50% | 0.25 |

> **Note on these numbers:** there is no human-labelled ground truth in
> this project. Rung 1 and rung 2 are compared against a reference model
> (Claude Opus, run manually) by **agreement**, not accuracy. Do not read
> "precision-analogue" or "recall-analogue" as correctness — the
> reference is itself an LLM, not a neutral judge.

## Privacy & data handling

| What | Handling |
|---|---|
| Raw resume file | Processed in memory, then discarded. Never stored. |
| Name / email / phone | Never stored by Compass. |
| Extracted skills + role scores | Stored, keyed by `user_id`. |
| Audit record | Always stored: input hash, taxonomy version, model version, prompt version, timestamp, output. Character-span offsets into the resume are part of the design but **not yet implemented** — known gap, not a shipped feature. |
| Resumes in this repo | Never committed. `resumes/`, `resumes_clean/`, `resumes_stripped_v2/` are all gitignored. |
| Cloud API calls on resume content | Approved only under a confirmed zero-retention agreement with the vendor. |

## Known limitations

- Audit-record span offsets are designed but not implemented (see above).
- `data_scientist` scores 1.000 on at least one real resume with nothing
  missing — a role a strong-but-typical candidate can max out cannot
  rank anyone; the core skill list may need revisiting.
- Consent status of some held-out evaluation resumes is unresolved,
  blocking a fully held-out evaluation number.
- `docs/labelling_rulebook.md` (rules R1–R9) has no rule for
  self-declared skills-list-only sections (no supporting
  project/experience evidence) — currently handled only as emergent
  behaviour by the reference model's evidence standard, not as a written
  rule.
- Image-layer PII (photos, scanned text-as-pixels) was found and fixed:
  the redaction pipeline now strips all embedded images and the
  verifier fails the gate if any survive. This was a real defect in an
  earlier demoed version; it's closed.

## Bucket status

| Bucket | Description | Status |
|---|---|---|
| B0 | Contract & scaffold | DONE |
| B1 | Golden set / hand-labelling | NOT DONE. Deliberately not pursued under a deadline; replaced by the reference-model comparison approach described above instead of human labels. |
| B2 | Taxonomy (skills.yaml, roles.yaml, 8 roles) | DONE |
| B3.0 | Thin-slice pipeline (PDF/DOCX -> text -> extract -> gate -> score -> top 5, CLI + Streamlit) | DONE |
| B3.1 | Rung 1 | DONE, shipped |
| B3.2 | Rung 2 | DONE, built and rejected (see above), stays in the codebase config-switchable |
| B3.3 | Rung 3 | NOT STARTED |
| B3.4 | Rung 4 as a live coded rung | NOT STARTED (manual reference-model comparison exists, see above, but that is not a coded rung) |
| B4 | Matching engine (deterministic, gated) | DONE, part of B3.0 |
| B5 | Evaluation harness | PARTIAL: a committed agreement-comparison script exists (`scripts/rung_compare.py`) and a grounding-check wrapper exists (`src/compass/eval/grounding.py`) using RAGAS's AspectCritic metric for whether an extracted skill is textually supported in the resume — but it has only ever been exercised against a mocked LLM in `tests/test_eval_grounding.py`; there is no committed script that runs it against a real model, and no API key is available yet. |
| B6 | Service packaging (FastAPI endpoint) | NOT STARTED |
| B7 | Report | v1 SHIPPED as an internal PDF report (not part of this repo). A v1.1 appendix is planned but explicitly **not yet authorised** to start. |

## How to run it

All commands run through `uv` — no pip, no manually activated virtualenvs.

```bash
# Run the test suite
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Validate the taxonomy files
uv run python scripts/validate_taxonomy.py

# Regenerate contracts/v1/*.schema.json from the pydantic models
uv run python scripts/export_schema.py

# Run the end-to-end thin slice on a resume (rule-based only)
uv run python scripts/run_thin_slice.py <path-to-resume.pdf>

# Launch the Streamlit UI
uv run streamlit run app/streamlit_app.py

# Reproduce the rung 1 vs rung 2 agreement comparison (see numbers above)
uv run python scripts/rung_compare.py --own-resume <path-to-your-resume>
```

Notes on the above, verified against the current repo rather than assumed:

- `run_thin_slice.py` and the Streamlit app both call
  `compass.pipeline.analyse_resume` and only exercise rung 1 extraction —
  neither has a flag to switch to rung 2.
- `rung_compare.py` requires `resumes_stripped_v2/prac_001.pdf`,
  `prac_006.pdf`, `prac_007.docx`, `prac_014.pdf`, and `prac_018.pdf` to
  exist locally (gitignored, not in the repo) in addition to the
  `--own-resume` path you pass in — it will not run standalone on a
  clean checkout.
- There is no committed script or CLI for the grounding harness
  (`src/compass/eval/grounding.py`); it is currently only reachable
  through its unit tests, which mock the LLM entirely. Treat "run the
  grounding harness" as not yet possible until that wrapper is wired
  into a script.
- No `[project.scripts]` entries are defined in `pyproject.toml` — every
  entry point above is invoked as `uv run python <script>` or
  `uv run <tool>`, not as an installed console command.

## Repo layout

```
src/compass/
  config.py          — settings loading (pydantic-settings + non-secret YAML defaults)
  pipeline.py         — analyse_resume(): the end-to-end rule-based pipeline
  contracts/           — v1 API request/response pydantic models (source of truth for contracts/v1/*.schema.json)
  eval/                — agreement metrics (rung_compare) and the RAGAS grounding wrapper
  extract/              — text extraction: PDF/DOCX text, gazetteer (rung 1), embeddings (rung 2), spans
  labels/               — hand-label file schema + loader (draft/final status, cross-validated against taxonomy)
  match/                — scorer.py: the gate + weighted coverage scoring engine
  resume_intake/         — hashing, PII scan, redaction, provenance, name-collision handling
  taxonomy/              — taxonomy loader + pydantic models

scripts/
  audit_images.py, strip_images.py, verify_redaction.py, verify_label_hashes.py, scan_pii.py — resume intake / redaction tooling
  check_name_collisions.py, hash_resumes.py, make_provenance.py — resume intake support
  make_label_stubs.py     — generates draft label file stubs under labels/
  report_orphan_skills.py  — taxonomy maintenance
  run_thin_slice.py        — end-to-end CLI entry point
  rung_compare.py           — rung 1 vs rung 2 agreement comparison against the reference model
  export_schema.py           — regenerates contracts/v1/*.schema.json from pydantic models
  validate_taxonomy.py        — taxonomy validation CLI

tests/
  test suite covering contracts, taxonomy, extraction (gazetteer/embeddings/spans/pdf), scoring,
  labels, resume intake (hashing/PII/redaction/provenance/name collisions), pipeline, and eval
  (agreement + grounding)

taxonomy/
  skills.yaml, roles.yaml — the versioned skill/role taxonomy (currently 0.6.0, 8 roles)

docs/
  labelling_rulebook.md — hand-labelling rules R1-R9 (see Known limitations for the gap)
```

Other top-level directories not listed above: `app/` (Streamlit UI),
`config/` (non-secret defaults), `contracts/` (generated JSON Schema +
examples), `data/golden/` and `eval/` (placeholders), `labels/practice/`
and `labels/exam/` (hand-label files, draft/final status per file).

## Local model server

Rung 3 (local open-weight LLM) will run through Ollama served in Docker,
bound to `127.0.0.1` only so it is never reachable from the network.
`docker-compose.yml` at the repo root defines the `ollama` service (GPU
passthrough, `ollama_models` named volume, healthcheck via `ollama list`).
No model is pulled yet — this only sets up the server.

```bash
# Start the server (detached)
docker compose up -d

# Stop the server (containers removed, ollama_models volume kept)
docker compose down

# Check status (look for "healthy")
docker compose ps

# View logs (look for the CUDA / GPU detection line)
docker compose logs ollama
```

## Roadmap / what's next

- **Rung 3** (local open-weight LLM): not started. Needs a licence check
  across the candidates (Qwen3, Gemma 3 12B, Phi-4-mini, Mistral Small
  3.1) before picking one.
- **Grounding harness real run**: blocked on an Anthropic/OpenAI API key
  not yet being available, and on wiring `src/compass/eval/grounding.py`
  into an actual runnable script (see How to run it).
- **B1 labelling**, if it restarts: would replace or supplement the
  reference-model agreement approach with real hand labels.
- **B6 service packaging**: FastAPI endpoint around the existing
  pipeline, not started.
- **B7 v1.1 appendix**: planned but explicitly not yet authorised to
  start.
