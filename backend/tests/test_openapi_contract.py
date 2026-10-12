"""Checks the FastAPI app has exactly the operations `openapi.yaml` names —
no missing and no extra (path, method) pairs. Path+method coverage only, not
exact response-schema equality — see issue #4's acceptance criteria."""

from __future__ import annotations

from pathlib import Path

import yaml

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

    # The app's `/health` route isn't part of openapi.yaml; ignore it here.
    app_ops.discard(("/health", "get"))

    missing = contract_ops - app_ops
    extra = app_ops - contract_ops
    assert not missing, f"Routes missing from the app: {sorted(missing)}"
    assert not extra, f"Routes present in the app but not in the contract: {sorted(extra)}"
