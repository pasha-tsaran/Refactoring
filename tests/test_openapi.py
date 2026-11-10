"""Validate OpenAPI and check real responses against its schemas."""

import importlib.util
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate
from user_api import create_app

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "go_server" / "api"


def test_openapi_is_valid_and_generated_files_match():
    spec = json.loads((API / "openapi.json").read_text(encoding="utf-8"))
    assert spec == yaml.safe_load(
        (API / "openapi.yaml").read_text(encoding="utf-8")
    )
    validate(spec)
    module_spec = importlib.util.spec_from_file_location(
        "generate_openapi", ROOT / "scripts" / "generate_openapi.py"
    )
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    assert module.build_spec() == spec


def test_real_responses_match_contract(tmp_path):
    spec = json.loads((API / "openapi.json").read_text(encoding="utf-8"))
    client = create_app(str(tmp_path / "contract.db")).test_client()
    user = client.post("/adduser", json={"name": "Contract"}).json
    samples = [
        ("/adduser", "post", 201, user),
        ("/user/{id}", "get", 200, client.get(f"/user/{user['id']}").json),
        (
            "/activate/{id}",
            "post",
            200,
            client.post(f"/activate/{user['id']}").json,
        ),
        ("/health", "get", 200, client.get("/health").json),
        ("/slow", "get", 202, client.get("/slow").json),
        ("/wrong", "get", 500, client.get("/wrong").json),
        (
            "/adduser",
            "post",
            400,
            client.post("/adduser", json={"name": ""}).json,
        ),
    ]
    for path, method, status, body in samples:
        schema = spec["paths"][path][method]["responses"][str(status)][
            "content"
        ]["application/json"]["schema"]
        Draft202012Validator(
            {**schema, "components": spec["components"]}
        ).validate(body)
