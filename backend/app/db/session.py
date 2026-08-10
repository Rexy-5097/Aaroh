"""Sanctioned database access layer.

This module is the ONLY place in Aaroh permitted to create a database
connection or pool (ADR-0061 I-12, enforced by .github/scripts/check_governance.py).

Everything else -- routes, services, domain logic, workers -- obtains a
connection from `request_transaction` and never constructs its own. A module
that builds its own connection has bypassed the transaction wrapper below, and
therefore bypassed the identity that row-level security depends on.

The wrapper implements ADR-0061 §1:

    BEGIN
      set request.jwt.claims (transaction-local)
      SET LOCAL ROLE authenticated
      ... application queries; auth.uid() resolves to the caller ...
    COMMIT

Why transaction-local and not session-level
-------------------------------------------
Both settings are established with transaction scope. `SET LOCAL` and
`set_config(..., is_local => true)` are reverted when the transaction ends,
whether it commits or rolls back. A plain `SET`, or a query issued outside a
transaction, would persist the identity on a pooled connection and hand it to
whichever request checked that connection out next. That is invariant I-3, and
`test_identity_does_not_leak_between_pooled_transactions` exists specifically to
prove it holds.

Why set_config() rather than SET LOCAL for the claims
-----------------------------------------------------
`SET LOCAL x = $1` cannot be parameterised -- the value would have to be
interpolated into SQL text, which is exactly the injection risk we refuse to
take with a value derived from a token. `set_config(name, value, true)` is an
ordinary function call, so the claims travel as a bound parameter.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg_pool import ConnectionPool

from app.auth.identity import VerifiedIdentity

# The database role every request-scoped statement executes as. It is not the
# login role: the login role holds no privileges of its own (NOINHERIT), so an
# identity must be established before anything is reachable.
REQUEST_ROLE = "authenticated"


class UnverifiedIdentityError(TypeError):
    """Raised when something other than a VerifiedIdentity reaches this layer.

    Slice 1 accepted a plain dict here and relied on the caller having verified
    it -- a convention, not a control. ADR-0063 replaces that with a type only
    the authentication package can produce, so "the caller must remember to
    verify" becomes "the database identity requires a verified identity object".
    """


def build_pool(dsn: str, *, min_size: int = 1, max_size: int = 4) -> ConnectionPool:
    """Create the application connection pool.

    The DSN must name a role WITHOUT the RLS-bypass attribute (ADR-0061 I-1).
    `test_app_role_cannot_bypass_rls` asserts this against the live database.
    """
    return ConnectionPool(dsn, min_size=min_size, max_size=max_size, open=True)


@contextmanager
def request_transaction(
    pool: ConnectionPool, identity: VerifiedIdentity
) -> Iterator[Connection]:
    """Yield a connection inside a transaction bound to the caller's identity.

    `identity` must be a VerifiedIdentity, which only the authentication package
    can construct (ADR-0063 I-19). A dict is refused: accepting one would make
    row-level security trust whatever the client asserted, turning the strongest
    control in the system into the weakest.

    Only `sub` and `role` reach PostgreSQL (ADR-0063 I-20). A real Supabase
    token also carries email, phone, user_metadata and app_metadata -- High-class
    data under standards/privacy.md, which would otherwise surface in
    pg_stat_activity, query logs, and error output.
    """
    if not isinstance(identity, VerifiedIdentity):
        raise UnverifiedIdentityError(
            "request_transaction requires a VerifiedIdentity from the "
            "authentication package; refusing to establish a database identity "
            "from an unverified value"
        )

    with pool.connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # Claims first, while still the login role -- then drop into the
                # lower-privileged role for the rest of the transaction.
                cur.execute(
                    "SELECT set_config('request.jwt.claims', %s, true)",
                    (json.dumps(identity.database_claims()),),
                )
                # Role names cannot be parameterised. REQUEST_ROLE is a module
                # constant and never derived from input.
                cur.execute(f"SET LOCAL ROLE {REQUEST_ROLE}")
            yield conn
