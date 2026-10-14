"""Checks the FastAPI app has exactly the operations `openapi.yaml` names —
no missing and no extra (path, method) pairs. Path+method coverage only, not
exact response-schema equality — see issue #4's acceptance criteria. The one
exception is `GET /health`, whose operationId, security, tags and response
schema are also checked against the real endpoint (issue #20)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = REPO_ROOT / "openapi.yaml"

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def _contract_operations() -> set[tuple[str, str]]:
    spec = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    operations: set[tuple[str, str]] = set()
    for path, methods in spec["paths"].items():
        for method in methods:
            if method.lower() in HTTP_METHODS:
                operations.add((path, method.lower()))
    return operations


def _app_operations() -> set[tuple[str, str]]:
    spec = app.openapi()
    operations: set[tuple[str, str]] = set()
    for path, methods in spec["paths"].items():
        for method in methods:
            if method.lower() in HTTP_METHODS:
                operations.add((path, method.lower()))
    return operations


def test_app_implements_every_contract_operation() -> None:
    contract_ops = _contract_operations()
    app_ops = _app_operations()

    missing = contract_ops - app_ops
    extra = app_ops - contract_ops
    assert not missing, f"Routes missing from the app: {sorted(missing)}"
    assert not extra, f"Routes present in the app but not in the contract: {sorted(extra)}"


def test_health_contract_matches_the_endpoint() -> None:
    spec: dict[str, Any] = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    operation = spec["paths"]["/health"]["get"]

    assert operation["operationId"] == "getHealth"
    # `security: []` opts out of the top-level bearerAuth: CI's curl and the
    # MCP health() tool call /health without a token.
    assert operation.get("security") == []
    assert operation["tags"] == ["Health"]

    ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    schema_name = ref.rsplit("/", 1)[-1]
    schema = spec["components"]["schemas"][schema_name]
    properties = schema["properties"]

    body = TestClient(app).get("/health").json()
    assert set(schema["required"]) == set(properties) == set(body)

    assert properties["status"]["enum"] == ["ok"]
    assert properties["commit"]["type"] == "string"
    assert properties["commit"].get("nullable") is True
