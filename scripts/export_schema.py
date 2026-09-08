"""Generate JSON Schema files from the pydantic v1 contract models.

Run with: uv run python scripts/export_schema.py

The models in src/compass/contracts/v1.py are the single source of truth.
Never hand-edit the generated *.schema.json files.
"""

from __future__ import annotations

import json
from pathlib import Path

from compass.contracts.v1 import ErrorResponse, Request, Response

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "contracts" / "v1"

MODELS = {
    "request": Request,
    "response": Response,
    "error": ErrorResponse,
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        schema = model.model_json_schema()
        out_path = OUTPUT_DIR / f"{name}.schema.json"
        out_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
