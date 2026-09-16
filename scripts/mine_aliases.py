"""Runs alias mining across the full resume corpus with a local Ollama model.

Loads corpus/UpdatedResumeDataSet.csv via compass.mining.corpus_loader, splits
it into char-budgeted batches, and sends each batch through
compass.mining.miner.run_mining_batch. Proposals are appended to --output
after each successful batch (read-modify-write over the whole JSON array, via
a temp file + atomic replace) so a crash mid-run only loses the batch that
was in flight, not prior ones. A failed batch is logged and skipped -- one
bad batch does not abort the run.

This script makes live Ollama calls. It is not exercised by the test suite.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

import ollama

from compass.extract.ollama_llm import DEFAULTS as RUNG3_DEFAULTS
from compass.mining.corpus_loader import batch_resumes, load_corpus
from compass.mining.miner import MiningBatchError, ProposalRecord, run_mining_batch
from compass.taxonomy.loader import load_taxonomy

ROOT = Path(__file__).resolve().parent.parent
TAXONOMY_DIR = ROOT / "taxonomy"
CORPUS_PATH = ROOT / "corpus" / "UpdatedResumeDataSet.csv"
DEFAULT_OUTPUT = ROOT / "corpus" / "proposals_raw.json"
CHAR_BUDGET = 9000
MODEL_CHOICES = ("qwen3:8b", "gemma4:e4b")


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


def append_records(output_path: Path, records: list[ProposalRecord]) -> None:
    """Read-modify-write the full proposals list, via a temp file + atomic
    replace so a crash mid-write cannot leave output_path truncated or
    half-written.
    """
    existing: list[dict] = []
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
    existing.extend(_record_to_dict(record) for record in records)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=output_path.parent, suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
        tmp_path.replace(output_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    taxonomy = load_taxonomy(TAXONOMY_DIR / "skills.yaml", TAXONOMY_DIR / "roles.yaml")

    resumes, duplicate_count = load_corpus(CORPUS_PATH)
    print(f"loaded {len(resumes)} unique resumes ({duplicate_count} duplicates dropped)")

    batches = batch_resumes(resumes, char_budget=args.char_budget)
    if args.limit_batches is not None:
        batches = batches[: args.limit_batches]
    total = len(batches)

    client = ollama.Client(
        host=RUNG3_DEFAULTS["host"], timeout=RUNG3_DEFAULTS["timeout_seconds"]
    )

    for batch_index, batch in enumerate(batches):
        try:
            records = run_mining_batch(
                batch, taxonomy, args.model, client, batch_index=batch_index
            )
        except MiningBatchError as exc:
            print(f"batch {batch_index + 1}/{total} ({args.model}): FAILED -- {exc}")
            continue

        append_records(args.output, records)
        print(f"batch {batch_index + 1}/{total} ({args.model}) -> {len(records)} proposals")

    return 0


if __name__ == "__main__":
    sys.exit(main())
