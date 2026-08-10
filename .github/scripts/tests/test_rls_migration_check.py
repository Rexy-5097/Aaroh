"""Regression coverage for check_rls_migrations (ADR-0061 I-5, ADR-0062 I-13).

The check reads migration SQL as text. It was hardened during Stage 0 slice 1
to normalise whitespace, because a literal substring match rejected a compliant
migration that aligned `FORCE  ROW LEVEL SECURITY` with two spaces -- and, far
worse, meant the I-5 requirement could be evaded by whitespace or a line break.

These tests pin both directions permanently: formatting variation must not
change the verdict, and every missing requirement must still fail.

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


COMPLIANT = """
CREATE TABLE public.widgets (
    user_id uuid PRIMARY KEY
);
ALTER TABLE public.widgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.widgets FORCE ROW LEVEL SECURITY;
CREATE POLICY widgets_own ON public.widgets
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());
"""


@pytest.fixture()
def run_check(tmp_path, monkeypatch):
    """Run check_rls_migrations against a throwaway migrations tree."""

    def _run(sql: str | None = None, *, filename: str = "0001_x.sql", py: str | None = None):
        migrations = tmp_path / "supabase" / "migrations"
        migrations.mkdir(parents=True, exist_ok=True)
        if sql is not None:
            (migrations / filename).write_text(sql, encoding="utf-8")
        if py is not None:
            (migrations / "0002_gen.py").write_text(py, encoding="utf-8")
        monkeypatch.setattr(check_governance, "REPO_ROOT", tmp_path)
        result = check_governance.Result()
        check_governance.check_rls_migrations(result)
        return result.failures

    return _run


# ── Formatting variation must not change the verdict ─────────────────────────

def test_1_standard_compliant_syntax_passes(run_check):
    assert run_check(COMPLIANT) == []


def test_2_multiple_spaces_passes(run_check):
    sql = COMPLIANT.replace("FORCE ROW LEVEL SECURITY", "FORCE  ROW  LEVEL   SECURITY")
    assert run_check(sql) == [], "extra spacing must not be read as a missing requirement"


def test_3_newline_formatting_variation_passes(run_check):
    sql = COMPLIANT.replace(
        "ALTER TABLE public.widgets FORCE ROW LEVEL SECURITY;",
        "ALTER TABLE public.widgets\n    FORCE\n    ROW LEVEL SECURITY;",
    )
    assert run_check(sql) == [], "a wrapped statement must not be read as absent"


# ── Every missing requirement must still fail ────────────────────────────────

def test_4_missing_enable_fails(run_check):
    sql = COMPLIANT.replace("ALTER TABLE public.widgets ENABLE ROW LEVEL SECURITY;", "")
    failures = run_check(sql)
    assert any("ENABLE ROW LEVEL SECURITY" in f for f in failures), failures


def test_5_missing_force_fails(run_check):
    sql = COMPLIANT.replace("ALTER TABLE public.widgets FORCE ROW LEVEL SECURITY;", "")
    failures = run_check(sql)
    assert any("FORCE ROW LEVEL SECURITY" in f for f in failures), failures


def test_6_missing_policy_fails(run_check):
    sql = """
    CREATE TABLE public.widgets (user_id uuid PRIMARY KEY);
    ALTER TABLE public.widgets ENABLE ROW LEVEL SECURITY;
    ALTER TABLE public.widgets FORCE ROW LEVEL SECURITY;
    """
    failures = run_check(sql)
    assert any("no policy" in f for f in failures), failures


def test_7_missing_with_check_fails(run_check):
    sql = COMPLIANT.replace("\n    WITH CHECK (user_id = auth.uid())", "")
    failures = run_check(sql)
    assert any("WITH CHECK" in f for f in failures), failures


# ── Adjacent requirements the same check owns ────────────────────────────────

def test_disabling_rls_fails(run_check):
    sql = COMPLIANT + "\nALTER TABLE public.widgets DISABLE ROW LEVEL SECURITY;\n"
    failures = run_check(sql)
    assert any("disables row level security" in f for f in failures), failures


def test_python_generated_ddl_fails(run_check):
    """ADR-0062 I-13: generated DDL would blind this check, so it is refused."""
    failures = run_check(COMPLIANT, py="from alembic import op\ndef upgrade():\n    op.create_table('t')\n")
    assert any("ADR-0062" in f for f in failures), failures


def test_a_migration_that_creates_nothing_is_not_flagged(run_check):
    """Data-only or grant-only migrations carry no table to protect."""
    assert run_check("GRANT SELECT ON public.widgets TO authenticated;") == []
