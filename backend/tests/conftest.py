"""Test fixtures for the RLS suite.

Applies the CI auth shim and every committed migration to a real PostgreSQL
instance, then exposes two seeded users and an application connection pool.

Nothing here talks to Supabase. The point is to exercise PostgreSQL's own
row-level security behaviour, which is what Supabase relies on.
"""

from __future__ import annotations

import os
import pathlib
import uuid

import psycopg
import pytest

from app.auth.testing import identity_for
from app.db.session import build_pool

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"
SHIM_SQL = pathlib.Path(__file__).resolve().parent / "sql" / "auth_shim.sql"

# Superuser DSN: applies the shim and migrations, and seeds auth.users.
ADMIN_DSN = os.environ.get(
    "AAROH_TEST_ADMIN_DSN",
    "postgresql://postgres:postgres@127.0.0.1:5432/aaroh_test",
)
# Application DSN: the role the backend connects as. No RLS bypass, NOINHERIT.
APP_DSN = os.environ.get(
    "AAROH_TEST_APP_DSN",
    "postgresql://aaroh_app:aaroh_app@127.0.0.1:5432/aaroh_test",
)

USER_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
USER_B = uuid.UUID("22222222-2222-4222-8222-222222222222")


def claims_for(user_id: uuid.UUID):
    """A VerifiedIdentity for RLS tests, via the sanctioned factory.

    ADR-0063 section 4a: these tests exercise the DATABASE boundary, so they use
    the factory rather than minting and verifying a JWT for every row-isolation
    assertion. The factory routes through the same validation the verifier uses,
    so it cannot produce an identity the verifier would reject.

    The complete authentication chain is proven separately and mandatorily in
    test_auth_end_to_end.py -- the factory stands in for that path, so that path
    must be tested for real somewhere.
    """
    return identity_for(user_id)


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Reset the schema, apply the shim, then every migration in order.

    The reset is what makes the suite deterministic and re-runnable against a
    persistent local cluster, not only against a throwaway CI container. Roles
    live at cluster level and survive; the shim creates them idempotently.
    """
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS auth CASCADE")
        conn.execute("CREATE SCHEMA public")

        conn.execute(SHIM_SQL.read_text(encoding="utf-8"))

        migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
        assert migrations, f"no migrations found in {MIGRATIONS_DIR}"
        for migration in migrations:
            conn.execute(migration.read_text(encoding="utf-8"))

        # Seed the two auth users the isolation tests act as.
        for user_id in (USER_A, USER_B):
            conn.execute(
                "INSERT INTO auth.users (id, email) VALUES (%s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (user_id, f"{user_id}@example.test"),
            )
    yield


@pytest.fixture()
def admin_conn():
    """Superuser connection, for asserting catalogue state and cleaning up."""
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        yield conn


@pytest.fixture()
def pool():
    """Application pool.

    max_size=1 is deliberate: it forces every transaction in a test to reuse
    the same physical connection, which is the precondition for the identity
    leak test to be meaningful rather than accidentally passing.
    """
    p = build_pool(APP_DSN, min_size=1, max_size=1)
    yield p
    p.close()


@pytest.fixture(autouse=True)
def clean_profiles(migrated_database):
    """Empty public.profiles before each test, as superuser."""
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute("DELETE FROM public.profiles")
    yield
