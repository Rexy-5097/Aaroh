"""Cross-user isolation and identity-leak tests (ADR-0061 Tier B).

Every test here asserts a NEGATIVE as well as a positive: it is not enough to
show a user can reach their own row. The suite must show the same code path
cannot reach anyone else's.
"""

from __future__ import annotations

import uuid

import psycopg
import pytest

from app.db.session import UnverifiedClaimsError, request_transaction
from conftest import APP_DSN, USER_A, USER_B, claims_for


def _seed(pool, user_id: uuid.UUID, name: str) -> None:
    with request_transaction(pool, claims_for(user_id)) as conn:
        conn.execute(
            "INSERT INTO public.profiles (user_id, display_name) VALUES (%s, %s)",
            (user_id, name),
        )


# ── Positive: each user reaches their own row ────────────────────────────────

def test_user_sees_own_row(pool):
    _seed(pool, USER_A, "alice")
    with request_transaction(pool, claims_for(USER_A)) as conn:
        rows = conn.execute("SELECT user_id, display_name FROM public.profiles").fetchall()
    assert rows == [(USER_A, "alice")]


def test_second_user_sees_own_row(pool):
    _seed(pool, USER_A, "alice")
    _seed(pool, USER_B, "bob")
    with request_transaction(pool, claims_for(USER_B)) as conn:
        rows = conn.execute("SELECT user_id, display_name FROM public.profiles").fetchall()
    assert rows == [(USER_B, "bob")]


def test_auth_uid_resolves_to_the_caller(pool):
    with request_transaction(pool, claims_for(USER_A)) as conn:
        assert conn.execute("SELECT auth.uid()").fetchone()[0] == USER_A


# ── Negative: no user reaches another's row ──────────────────────────────────

def test_user_cannot_read_other_users_row(pool):
    _seed(pool, USER_A, "alice")
    _seed(pool, USER_B, "bob")
    with request_transaction(pool, claims_for(USER_A)) as conn:
        rows = conn.execute(
            "SELECT user_id FROM public.profiles WHERE user_id = %s", (USER_B,)
        ).fetchall()
    # RLS filters rather than errors: B's row is simply not visible to A.
    assert rows == []


def test_user_cannot_update_other_users_row(pool):
    _seed(pool, USER_B, "bob")
    with request_transaction(pool, claims_for(USER_A)) as conn:
        cur = conn.execute(
            "UPDATE public.profiles SET display_name = %s WHERE user_id = %s",
            ("hijacked", USER_B),
        )
        assert cur.rowcount == 0

    with request_transaction(pool, claims_for(USER_B)) as conn:
        assert conn.execute(
            "SELECT display_name FROM public.profiles"
        ).fetchone()[0] == "bob"


def test_other_user_cannot_update_first_users_row(pool):
    _seed(pool, USER_A, "alice")
    with request_transaction(pool, claims_for(USER_B)) as conn:
        cur = conn.execute(
            "UPDATE public.profiles SET display_name = %s WHERE user_id = %s",
            ("hijacked", USER_A),
        )
        assert cur.rowcount == 0


def test_user_cannot_delete_other_users_row(pool):
    _seed(pool, USER_B, "bob")
    with request_transaction(pool, claims_for(USER_A)) as conn:
        cur = conn.execute("DELETE FROM public.profiles WHERE user_id = %s", (USER_B,))
        assert cur.rowcount == 0

    with request_transaction(pool, claims_for(USER_B)) as conn:
        assert conn.execute("SELECT count(*) FROM public.profiles").fetchone()[0] == 1


def test_user_cannot_insert_row_owned_by_another(pool):
    """WITH CHECK, not USING, is what stops this. A policy with only USING
    would permit writing a row the writer can never see."""
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with request_transaction(pool, claims_for(USER_A)) as conn:
            conn.execute(
                "INSERT INTO public.profiles (user_id, display_name) VALUES (%s, %s)",
                (USER_B, "planted"),
            )


def test_user_cannot_reassign_own_row_to_another(pool):
    """UPDATE's WITH CHECK must block moving ownership away."""
    _seed(pool, USER_A, "alice")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with request_transaction(pool, claims_for(USER_A)) as conn:
            conn.execute(
                "UPDATE public.profiles SET user_id = %s WHERE user_id = %s",
                (USER_B, USER_A),
            )


# ── The invariant that matters most: I-3, identity must not leak ─────────────

def test_identity_does_not_leak_between_pooled_transactions(pool):
    """Two sequential transactions on the SAME physical connection.

    The pool is capped at one connection, so this reuse is guaranteed rather
    than incidental. If the wrapper used plain SET instead of SET LOCAL, the
    second transaction would still be acting as user A.
    """
    _seed(pool, USER_A, "alice")
    _seed(pool, USER_B, "bob")

    with request_transaction(pool, claims_for(USER_A)) as conn:
        first_uid = conn.execute("SELECT auth.uid()").fetchone()[0]
        first_rows = conn.execute("SELECT user_id FROM public.profiles").fetchall()

    with request_transaction(pool, claims_for(USER_B)) as conn:
        second_uid = conn.execute("SELECT auth.uid()").fetchone()[0]
        second_rows = conn.execute("SELECT user_id FROM public.profiles").fetchall()

    assert first_uid == USER_A
    assert second_uid == USER_B
    assert first_rows == [(USER_A,)]
    assert second_rows == [(USER_B,)]


def test_identity_is_cleared_after_the_transaction(pool):
    """Outside the wrapper the connection carries no identity and no role."""
    with request_transaction(pool, claims_for(USER_A)) as conn:
        assert conn.execute("SELECT auth.uid()").fetchone()[0] == USER_A

    with pool.connection() as conn:
        assert conn.execute("SELECT current_setting('request.jwt.claims', true)").fetchone()[0] in (None, "")
        assert conn.execute("SELECT current_user").fetchone()[0] == "aaroh_app"


def test_rollback_leaves_the_connection_safe(pool):
    """A failed transaction must not strand an identity on the connection."""
    with pytest.raises(psycopg.errors.UndefinedTable):
        with request_transaction(pool, claims_for(USER_A)) as conn:
            conn.execute("SELECT * FROM public.table_that_does_not_exist")

    with pool.connection() as conn:
        # The role reverted, and the transaction-local claims did not survive.
        assert conn.execute("SELECT current_user").fetchone()[0] == "aaroh_app"
        assert conn.execute(
            "SELECT current_setting('request.jwt.claims', true)"
        ).fetchone()[0] in (None, "")

    # Stronger still: with no role assumed, the identity function is not even
    # reachable. aaroh_app is NOINHERIT and holds no USAGE on the auth schema,
    # so a caller outside the wrapper cannot so much as ask who it is.
    with pool.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT auth.uid()")


# ── No identity established means no access at all ───────────────────────────

def test_raw_connection_without_the_wrapper_has_no_access(pool):
    """Bypassing request_transaction must fail closed.

    aaroh_app is NOINHERIT, so it holds none of `authenticated`'s privileges
    until it explicitly assumes the role. This is what makes I-12 enforceable
    rather than merely advisory.
    """
    _seed(pool, USER_A, "alice")
    with pool.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM public.profiles")


def test_anon_role_has_no_access(pool):
    _seed(pool, USER_A, "alice")
    with psycopg.connect(APP_DSN) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE anon")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT * FROM public.profiles")


# ── Claims that are not usable as an identity are refused ────────────────────

@pytest.mark.parametrize(
    "claims",
    [{}, {"sub": ""}, {"sub": None}, {"sub": "not-a-uuid"}, {"role": "authenticated"}],
)
def test_unusable_claims_are_refused_before_any_query(pool, claims):
    with pytest.raises(UnverifiedClaimsError):
        with request_transaction(pool, claims):
            pytest.fail("a session was opened for claims carrying no usable subject")
