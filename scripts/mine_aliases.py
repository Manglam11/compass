"""Runs alias mining across the full resume corpus with a local Ollama model.

Loads corpus/UpdatedResumeDataSet.csv via compass.mining.corpus_loader, splits
it into char-budgeted batches, and sends each batch through
compass.mining.miner.run_mining_batch. Proposals are appended to --output
after each successful batch (read-modify-write over the whole JSON array, via
a temp file + atomic replace) so a crash mid-run only loses the batch that
was in flight, not prior ones. A failed batch is logged and skipped -- one
bad batch does not abort the run, but it does mark the run as failed: a
<output>.manifest.json is always written (even if every batch fails) with the
model/config used, batch counts, and per-batch failure details, and the
process exits 1 if any batch failed. The proposals file itself is also
always written, as an empty list if there are no proposals -- a run must
never be silently indistinguishable from a run that never happened.

This script makes live Ollama calls. It is not exercised by the test suite.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import ollama

from compass.extract.ollama_llm import DEFAULTS as RUNG3_DEFAULTS
from compass.mining.corpus_loader import batch_resumes, load_corpus
from compass.mining.miner import (
    NUM_PREDICT,
    MiningBatchError,
    ProposalRecord,
    run_mining_batch,
)
from compass.taxonomy.loader import load_taxonomy

ROOT = Path(__file__).resolve().parent.parent
TAXONOMY_DIR = ROOT / "taxonomy"
CORPUS_PATH = ROOT / "corpus" / "UpdatedResumeDataSet.csv"
DEFAULT_OUTPUT = ROOT / "corpus" / "proposals_raw.json"
CHAR_BUDGET = 9000
MODEL_CHOICES = ("gemma4:e4b",)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", choices=MODEL_CHOICES, required=True, help="Ollama model to mine with."
    )
    parser.add_argument(
        "--limit-batches",
        type=int,
        default=None,
        help="Only run the first N batches (for a pilot run).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--char-budget",
        type=int,
        default=CHAR_BUDGET,
        help=f"Max characters per batch (default: {CHAR_BUDGET}).",
    )
    return parser.parse_args(argv)


def _record_to_dict(record: ProposalRecord) -> dict:
    data = asdict(record)
    if data["suggested_name"] is None:
        del data["suggested_name"]
    return data


def _atomic_write_json(path: Path, data: object) -> None:
    """Write data to path via a temp file + atomic replace so a crash
    mid-write cannot leave path truncated or half-written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def append_records(output_path: Path, records: list[ProposalRecord]) -> None:
    """Read-modify-write the full proposals list, via a temp file + atomic
    replace so a crash mid-write cannot leave output_path truncated or
    half-written.
    """
    existing: list[dict] = []
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
    existing.extend(_record_to_dict(record) for record in records)
    _atomic_write_json(output_path, existing)


def _manifest_path(output_path: Path) -> Path:
    return output_path.parent / f"{output_path.stem}.manifest.json"


def _git_head_short() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started_at = datetime.now(UTC)

    taxonomy = load_taxonomy(TAXONOMY_DIR / "skills.yaml", TAXONOMY_DIR / "roles.yaml")

    resumes, duplicate_count = load_corpus(CORPUS_PATH)
    rows_unique = len(resumes)
    rows_total = rows_unique + duplicate_count
    print(f"loaded {rows_unique} unique resumes ({duplicate_count} duplicates dropped)")

    batches = batch_resumes(resumes, char_budget=args.char_budget)
    if args.limit_batches is not None:
        batches = batches[: args.limit_batches]
    total = len(batches)

    client = ollama.Client(host=RUNG3_DEFAULTS["host"], timeout=RUNG3_DEFAULTS["timeout_seconds"])

    manifest_path = _manifest_path(args.output)
    if not args.output.exists():
        _atomic_write_json(args.output, [])

    batches_ok = 0
    proposals_count = 0
    failures: list[dict] = []

    try:
        for batch_index, batch in enumerate(batches):
            try:
                records = run_mining_batch(
                    batch, taxonomy, args.model, client, batch_index=batch_index
                )
            except MiningBatchError as exc:
                print(f"batch {batch_index + 1}/{total} ({args.model}): FAILED -- {exc}")
                failures.append(
                    {
                        "batch_index": batch_index,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                continue

            append_records(args.output, records)
            proposals_count += len(records)
            batches_ok += 1
            print(f"batch {batch_index + 1}/{total} ({args.model}) -> {len(records)} proposals")
    finally:
        finished_at = datetime.now(UTC)
        batches_failed = len(failures)
        manifest = {
            "model": args.model,
            "config": {
                "char_budget": args.char_budget,
                "num_predict": NUM_PREDICT,
                "num_ctx": RUNG3_DEFAULTS["num_ctx"],
                "temperature": RUNG3_DEFAULTS["temperature"],
                "seed": RUNG3_DEFAULTS["seed"],
            },
            "corpus": {
                "rows_total": rows_total,
                "rows_unique_after_dedup": rows_unique,
            },
            "batches_total": total,
            "batches_ok": batches_ok,
            "batches_failed": batches_failed,
            "failures": failures,
            "proposals_count": proposals_count,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "git_head": _git_head_short(),
        }
        _atomic_write_json(manifest_path, manifest)

    batches_failed = len(failures)
    print(
        f"batches: {batches_ok} ok, {batches_failed} failed, {total} total -- "
        f"manifest: {manifest_path}"
    )
    return 1 if batches_failed else 0


if __name__ == "__main__":
    sys.exit(main())
