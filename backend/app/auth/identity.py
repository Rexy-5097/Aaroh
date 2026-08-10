"""The verified identity type (ADR-0063 section 4).

What this type guarantees, precisely
------------------------------------
It carries a subject and role that a cryptographic verification path produced.
Construction requires a module-private sentinel, so writing
`VerifiedIdentity(subject=..., role=...)` from application code raises rather
than silently succeeding.

What it does NOT guarantee
--------------------------
Python has no private constructor. A determined caller can reach the sentinel
through `sys.modules`, or bypass `__init__` entirely with `object.__new__`.
This type is therefore NOT unforgeable, and no comment or test here should
claim otherwise.

The real guarantee is two-layered:
  1. runtime  -- accidental construction fails loudly (this module);
  2. static   -- deliberate construction outside `app.auth` fails CI
                 (check_governance.py, invariant I-19).

Overclaiming a boundary is worse than documenting its limits, because it stops
people looking at it.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from .errors import UnauthorizedIdentityConstruction

# Module-private sentinel. Not exported in __all__ and not re-exported by the
# package. Reaching it from outside this module is possible but unmistakably
# deliberate -- which is the point: the static check catches deliberate.
_CONSTRUCTION_SENTINEL = object()

# The only role Aaroh accepts. `anon` and `service_role` are rejected by
# requiring equality with this value rather than by naming them (ADR-0063
# section 2) -- an allow-list of one is stricter than a deny-list of two.
AUTHENTICATED_ROLE = "authenticated"


class VerifiedIdentity:
    """Immutable, minimal, verified identity.

    Holds only what the database boundary needs (ADR-0063 section 5): the
    subject and the role. It deliberately does NOT carry email, phone,
    session_id, or metadata, so those cannot reach PostgreSQL by accident.
    """

    __slots__ = ("_subject", "_role")

    def __init__(self, subject: Any, role: str, *, _sentinel: Any = None) -> None:
        if _sentinel is not _CONSTRUCTION_SENTINEL:
            raise UnauthorizedIdentityConstruction(
                "VerifiedIdentity may only be constructed by the authentication "
                "package. Obtain one from the verifier, or from app.auth.testing "
                "in tests. See ADR-0063 I-19."
            )
        object.__setattr__(self, "_subject", subject)
        object.__setattr__(self, "_role", role)

    # -- immutability ---------------------------------------------------------
    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("VerifiedIdentity is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("VerifiedIdentity is immutable")

    # -- accessors ------------------------------------------------------------
    @property
    def subject(self) -> UUID:
        return self._subject

    @property
    def role(self) -> str:
        return self._role

    def database_claims(self) -> dict[str, str]:
        """Exactly what may enter `request.jwt.claims` (ADR-0063 I-20).

        This method is the single place the database payload is built, so
        widening it is a visible, reviewable change rather than a diffuse one.
        """
        return {"sub": str(self._subject), "role": self._role}

    def __repr__(self) -> str:
        # Subject is a user identifier; keep it out of logs and tracebacks.
        return f"VerifiedIdentity(subject=<redacted>, role={self._role!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VerifiedIdentity):
            return NotImplemented
        return self._subject == other._subject and self._role == other._role

    def __hash__(self) -> int:
        return hash((self._subject, self._role))


def _build(subject: Any, role: str) -> VerifiedIdentity:
    """Sanctioned construction. Package-internal by convention and by I-19.

    Applies the same subject validation everywhere, so no caller -- verifier or
    test factory -- can produce an identity the other would have rejected.
    """
    if not isinstance(subject, UUID):
        try:
            subject = UUID(str(subject))
        except (ValueError, TypeError, AttributeError) as exc:
            raise UnauthorizedIdentityConstruction(
                "subject is not a valid UUID"
            ) from exc
    if role != AUTHENTICATED_ROLE:
        raise UnauthorizedIdentityConstruction(
            f"role must be {AUTHENTICATED_ROLE!r}"
        )
    return VerifiedIdentity(subject, role, _sentinel=_CONSTRUCTION_SENTINEL)
