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
from uuid import UUID

from psycopg import Connection
from psycopg_pool import ConnectionPool

# The database role every request-scoped statement executes as. It is not the
# login role: the login role holds no privileges of its own (NOINHERIT), so an
# identity must be established before anything is reachable.
REQUEST_ROLE = "authenticated"


class UnverifiedClaimsError(RuntimeError):
    """Raised when claims are unusable as a database identity.

    The caller is responsible for having already verified the token's
    signature, expiry, issuer and audience (ADR-0061 I-4). This class is the
    last line of defence, not the verification step: it only checks that the
    claims carry a subject of the right shape.
    """


def build_pool(dsn: str, *, min_size: int = 1, max_size: int = 4) -> ConnectionPool:
    """Create the application connection pool.

    The DSN must name a role WITHOUT the RLS-bypass attribute (ADR-0061 I-1).
    `test_app_role_cannot_bypass_rls` asserts this against the live database.
    """
    return ConnectionPool(dsn, min_size=min_size, max_size=max_size, open=True)


def _require_subject(claims: dict) -> str:
    """Return the subject from already-verified claims, or refuse."""
    subject = claims.get("sub")
    if subject is None or subject == "":
        raise UnverifiedClaimsError("claims carry no 'sub'; refusing to open a session")
    try:
        UUID(str(subject))
    except (ValueError, AttributeError, TypeError) as exc:
        raise UnverifiedClaimsError("claims 'sub' is not a UUID") from exc
    return str(subject)


@contextmanager
def request_transaction(pool: ConnectionPool, claims: dict) -> Iterator[Connection]:
    """Yield a connection inside a transaction bound to the caller's identity.

    `claims` MUST already be cryptographically verified. Passing unverified
    claims here would make row-level security trust whatever the client
    asserted, turning the strongest control in the system into the weakest.
    """
    _require_subject(claims)

    with pool.connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                # Claims first, while still the login role -- then drop into the
                # lower-privileged role for the rest of the transaction.
                cur.execute(
                    "SELECT set_config('request.jwt.claims', %s, true)",
                    (json.dumps(claims),),
                )
                # Role names cannot be parameterised. REQUEST_ROLE is a module
                # constant and never derived from input.
                cur.execute(f"SET LOCAL ROLE {REQUEST_ROLE}")
            yield conn
