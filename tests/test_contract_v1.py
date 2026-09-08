"""Tests for the v1 contract. Loads examples from contracts/v1/examples/."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from compass.contracts.v1 import ErrorResponse, Request, Response, RoleMatch

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "contracts" / "v1" / "examples"


def load_example(name: str) -> dict:
    with (EXAMPLES_DIR / f"{name}.example.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def test_valid_request_example_parses():
    data = load_example("request")
    request = Request.model_validate(data)
    assert request.schema_version == "v1"


def test_valid_response_example_parses():
    data = load_example("response")
    response = Response.model_validate(data)
    assert response.schema_version == "v1"


def test_error_example_parses():
    data = load_example("error")
    error = ErrorResponse.model_validate(data)
    assert error.schema_version == "v1"


def test_request_with_wrong_schema_version_rejected():
    data = load_example("request")
    data["schema_version"] = "v2"
    with pytest.raises(ValidationError):
        Request.model_validate(data)


def test_role_match_score_out_of_range_rejected():
    data = load_example("response")
    bad_match = dict(data["matches"][0])
    bad_match["score"] = 1.4
    with pytest.raises(ValidationError):
        RoleMatch.model_validate(bad_match)


def test_unknown_extra_field_rejected():
    data = load_example("request")
    data["unexpected_field"] = "surprise"
    with pytest.raises(ValidationError):
        Request.model_validate(data)


def test_response_has_no_confidence_or_email_field():
    field_names = set(Response.model_fields.keys())
    assert "confidence" not in field_names
    assert "email" not in field_names


def test_round_trip_model_json_model_identical():
    data = load_example("response")
    response = Response.model_validate(data)
    round_tripped = Response.model_validate_json(response.model_dump_json())
    assert response == round_tripped
