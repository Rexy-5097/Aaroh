"""Regression coverage for check_domain_purity (ADR-0067).

The check exists because `check_engine_purity` cannot see a transitive
impurity. It inspects only files inside the decision-engine package, so a
future `rank()` importing `app.domain.snapshot` passes even if that module
imports psycopg -- the forbidden import is one hop away and invisible.

These tests pin both directions permanently: a pure domain module must pass,
and every class of impurity must still fail. A check that only ever passes is
indistinguishable from one that is broken, so the violating fixtures matter
more than the compliant one.

No database is required. This runs in the `governance` CI job.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "check_governance.py"
_spec = importlib.util.spec_from_file_location("check_governance", SCRIPT)
check_governance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_governance)


COMPLIANT = '''
"""A pure domain module: plain data, injected time, no I/O."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Thing:
    at: datetime
    count: int


def build(*, as_of: datetime, rows) -> Thing:
    return Thing(at=as_of, count=len(rows))
'''


@pytest.fixture()
def run_check(tmp_path, monkeypatch):
    """Run check_domain_purity against a throwaway domain package."""

    def _run(source: str | None = COMPLIANT, *, filename: str = "thing.py"):
        domain = tmp_path / "backend" / "app" / "domain"
        domain.mkdir(parents=True, exist_ok=True)
        if source is not None:
            (domain / filename).write_text(source, encoding="utf-8")
        monkeypatch.setattr(check_governance, "REPO_ROOT", tmp_path)
        result = check_governance.Result()
        check_governance.check_domain_purity(result)
        return result

    return _run


# ── The compliant direction ──────────────────────────────────────────────────

def test_a_pure_domain_module_passes(run_check):
    result = run_check()
    assert not result.failures
    assert any("pure" in line for line in result.lines)


def test_ordinary_pure_imports_are_allowed(run_check):
    """The check must not be so blunt that pure code cannot be written."""
    result = run_check(
        "import re\n"
        "import json\n"
        "from dataclasses import dataclass\n"
        "from datetime import datetime, timezone\n"
        "from uuid import UUID\n"
        "from collections.abc import Iterable\n"
        "from app.domain.other import THING\n"
    )
    assert not result.failures


def test_the_check_is_armed_when_no_domain_package_exists(tmp_path, monkeypatch):
    """It reports ARMED rather than passing vacuously, so an absent package is
    never mistaken for a clean one."""
    monkeypatch.setattr(check_governance, "REPO_ROOT", tmp_path)
    result = check_governance.Result()
    check_governance.check_domain_purity(result)
    assert not result.failures
    assert any("ARMED" in line for line in result.lines)


# ── The violating direction ──────────────────────────────────────────────────

@pytest.mark.parametrize(
    "statement",
    [
        "import psycopg",
        "import psycopg2",
        "from psycopg import Connection",
        "import psycopg_pool",
        "from psycopg_pool import ConnectionPool",
        "import sqlalchemy",
        "import asyncpg",
        "import supabase",
    ],
)
def test_a_database_import_fails(run_check, statement):
    """The snapshot is the engine's input; a database import here would give
    the engine a hidden input one hop away from its own purity check."""
    assert run_check(statement + "\n").failures


@pytest.mark.parametrize(
    "statement",
    ["import fastapi", "from fastapi import APIRouter", "import starlette",
     "from pydantic import BaseModel"],
)
def test_an_http_or_framework_import_fails(run_check, statement):
    """Domain types must be usable with no web framework present."""
    assert run_check(statement + "\n").failures


@pytest.mark.parametrize("statement", ["import jwt", "from jwt import decode", "import jose"])
def test_an_authentication_import_fails(run_check, statement):
    assert run_check(statement + "\n").failures


@pytest.mark.parametrize(
    "statement",
    ["import requests", "import httpx", "import urllib.request", "import socket",
     "import aiohttp"],
)
def test_a_network_import_fails(run_check, statement):
    assert run_check(statement + "\n").failures


@pytest.mark.parametrize("statement", ["import openai", "import anthropic", "import litellm"])
def test_an_ai_provider_import_fails(run_check, statement):
    """The engine decides and the LLM explains (ADR-0059). A provider reachable
    from the engine's input would make that boundary a convention again."""
    assert run_check(statement + "\n").failures


@pytest.mark.parametrize(
    "statement",
    ["from app.db.session import request_transaction",
     "from app.db import snapshot",
     "from app.http.schemas import Thing",
     "from app.auth.identity import VerifiedIdentity"],
)
def test_reaching_back_into_an_outer_layer_fails(run_check, statement):
    """The dependency runs one way: db/ and http/ import domain/, never the
    reverse. This is the check that keeps it that way."""
    assert run_check(statement + "\n").failures


# ── Hidden inputs, not just imports ──────────────────────────────────────────

@pytest.mark.parametrize(
    "call",
    ["datetime.now()", "datetime.utcnow()", "time.time()", "os.getenv('X')",
     "random.random()", "random.shuffle([])", "uuid.uuid4()"],
)
def test_a_hidden_or_non_deterministic_input_fails(run_check, call):
    """`as_of` is an input, never read internally (ADR-0059, ADR-0067 section 5).
    A builder that reads a clock makes every snapshot unreproducible."""
    assert run_check(f"def go():\n    return {call}\n").failures


def test_the_failure_message_names_the_file_and_line(run_check):
    """A check that fails without saying where teaches people to disable it."""
    result = run_check("from dataclasses import dataclass\nimport psycopg\n")
    assert result.failures
    assert "thing.py:2" in result.failures[0]
    assert "psycopg" in result.failures[0]


def test_an_unparseable_domain_module_fails_rather_than_being_skipped(run_check):
    """Silently skipping a file it cannot read would make the check evadable by
    writing something it cannot parse."""
    assert run_check("def broken(:\n").failures


# ── The check must not drift from the engine's own list ──────────────────────

def test_every_engine_forbidden_import_is_also_forbidden_in_the_domain(run_check):
    """The domain list is built FROM the engine list, so adding a module there
    covers both. This pins that relationship rather than trusting it.

    Each entry is imported by its full dotted name. Asserting on the top-level
    name instead would be wrong for `google.generativeai`: bare `google` is a
    namespace package shared by unrelated libraries, and forbidding it would
    reject imports that are not the AI SDK at all.
    """
    for module in sorted(check_governance.ENGINE_FORBIDDEN_IMPORTS):
        assert run_check(f"import {module}\n").failures, f"{module} is allowed in domain/"
        assert run_check(f"from {module} import thing\n").failures, \
            f"from-import of {module} is allowed in domain/"
