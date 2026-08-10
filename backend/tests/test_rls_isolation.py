"""Cross-user isolation and identity-leak tests (ADR-0061 Tier B).

Every test here asserts a NEGATIVE as well as a positive: it is not enough to
show a user can reach their own row. The suite must show the same code path
cannot reach anyone else's.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager

import psycopg
import pytest

from app.db.session import UnverifiedIdentityError, build_pool, request_transaction
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
    """Identity established in one transaction must not survive into the next
    use of the SAME physical connection.

    Why phase 2 exists
    ------------------
    An earlier version of this test ran two *wrapped* transactions back to back
    and asserted each saw its own rows. That version passed even when SET LOCAL
    was mutated to a persistent SET, because the second transaction set its own
    claims and simply overwrote the leaked ones. The test's name promised a
    property its assertions never exercised.

    The leak is only observable from a transaction that establishes NO identity
    of its own. Phase 2 is that observation point, and it is what makes this
    test mutation-sensitive. `test_persistent_set_is_observable_as_a_leak`
    proves these exact assertions fail under the mutation.

    Physical connection reuse is asserted via pg_backend_pid() rather than
    assumed from the pool being capped at one. If the fixture ever stops
    reusing the connection, this test fails loudly instead of passing vacuously.
    """
    _seed(pool, USER_A, "alice")
    _seed(pool, USER_B, "bob")

    # Phase 1 -- user A, through the sanctioned wrapper.
    with request_transaction(pool, claims_for(USER_A)) as conn:
        pid_a = conn.execute("SELECT pg_backend_pid()").fetchone()[0]
        assert conn.execute("SELECT auth.uid()").fetchone()[0] == USER_A
        assert conn.execute("SELECT user_id FROM public.profiles").fetchall() == [(USER_A,)]

    # Phase 2 -- same connection, NO identity established. Nothing here sets
    # claims or a role, so nothing may be inherited from phase 1.
    with pool.connection() as conn:
        pid_unwrapped = conn.execute("SELECT pg_backend_pid()").fetchone()[0]
        leaked_claims = conn.execute(
            "SELECT current_setting('request.jwt.claims', true)"
        ).fetchone()[0]
        leaked_role = conn.execute("SELECT current_user").fetchone()[0]

    assert pid_unwrapped == pid_a, (
        "the pool did not reuse the physical connection; this test cannot prove "
        "anything about leakage between reuses"
    )
    assert leaked_claims in (None, ""), (
        f"user A's claims survived onto a reused connection: {leaked_claims!r}"
    )
    assert leaked_role == "aaroh_app", (
        f"user A's role survived onto a reused connection: {leaked_role}"
    )

    # Phase 3 -- user B, same connection, through the wrapper.
    with request_transaction(pool, claims_for(USER_B)) as conn:
        pid_b = conn.execute("SELECT pg_backend_pid()").fetchone()[0]
        assert pid_b == pid_a, "connection not reused for phase 3"
        assert conn.execute("SELECT auth.uid()").fetchone()[0] == USER_B
        assert conn.execute("SELECT user_id FROM public.profiles").fetchall() == [(USER_B,)]


@contextmanager
def _leaky_transaction(pool, claims: dict):
    """A deliberately WRONG variant of request_transaction.

    Uses session-scoped settings -- set_config(..., false) and a bare SET ROLE --
    instead of transaction-local ones. This is exactly the mutation ADR-0061 I-3
    forbids. It exists only so the test below can demonstrate, permanently and
    in CI, that the identity-leak test detects it, rather than that detection
    resting on a mutation somebody ran by hand once.
    """
    with pool.connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT set_config('request.jwt.claims', %s, false)",
                    (json.dumps(claims.database_claims()),),
                )
                cur.execute("SET ROLE authenticated")
            yield conn


def test_persistent_set_is_observable_as_a_leak():
    """Targeted mutation proof for the identity-leak test above.

    Runs the leaky variant, then makes the SAME observations the real test
    makes. Under the mutation those observations show a leak -- which is
    precisely why the real test fails when the implementation regresses.

    Uses a private pool so the poisoned session state cannot escape into any
    other test.
    """
    leaky_pool = build_pool(APP_DSN, min_size=1, max_size=1)
    try:
        with _leaky_transaction(leaky_pool, claims_for(USER_A)) as conn:
            pid_a = conn.execute("SELECT pg_backend_pid()").fetchone()[0]

        with leaky_pool.connection() as conn:
            pid_after = conn.execute("SELECT pg_backend_pid()").fetchone()[0]
            leaked_claims = conn.execute(
                "SELECT current_setting('request.jwt.claims', true)"
            ).fetchone()[0]
            leaked_role = conn.execute("SELECT current_user").fetchone()[0]

        assert pid_after == pid_a, "connection not reused; mutation proof inconclusive"

        # The real test asserts `leaked_claims in (None, "")` and
        # `leaked_role == "aaroh_app"`. Both are violated here, so the real test
        # would fail against this implementation.
        assert leaked_claims not in (None, ""), (
            "persistent SET did not leak claims; this proof no longer demonstrates "
            "what the identity-leak test guards against"
        )
        assert str(USER_A) in leaked_claims
        assert leaked_role == "authenticated", (
            "persistent SET ROLE did not leak the role; proof inconclusive"
        )
    finally:
        leaky_pool.close()


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


# ── Only a VerifiedIdentity may establish a database identity ────────────────
#
# Slice 1 accepted a dict here and validated its `sub` -- a convention. ADR-0063
# replaces that with a type the authentication package alone can construct, so
# these cases now assert the stronger property: an unverified value of ANY shape
# is refused before a single statement runs.

@pytest.mark.parametrize(
    "unverified",
    [
        {},
        {"sub": ""},
        {"sub": None},
        {"sub": "not-a-uuid"},
        {"role": "authenticated"},
        # A dict that looks exactly like a verified identity is still refused:
        # plausibility is not verification.
        {"sub": str(USER_A), "role": "authenticated"},
        None,
        "a-bare-string",
        42,
    ],
)
def test_unverified_values_are_refused_before_any_query(pool, unverified):
    with pytest.raises(UnverifiedIdentityError):
        with request_transaction(pool, unverified):
            pytest.fail("a session was opened for an unverified value")
