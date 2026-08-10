"""Sanctioned test-only identity factory (ADR-0063 section 4a).

PRODUCTION CODE MUST NEVER IMPORT THIS MODULE.

That is invariant I-23 and is enforced statically by
.github/scripts/check_governance.py. The prohibition exists because this module
hands out identities without any cryptographic verification -- exactly what the
verifier is there to prevent.

Why it exists at all
--------------------
The RLS suite tests the DATABASE boundary. Forcing every one of those tests to
mint and verify a JWT would couple row-isolation tests to key fixtures and
signature machinery, so a policy bug and a signature bug would look alike.

The alternative -- exempting tests from the construction rule -- was rejected:
a blanket exemption inside a security boundary is the mistake slice 1's review
removed when it deleted NON_USER_OWNED_TABLES.

This factory routes through the SAME `_build` the verifier uses, so it applies
identical subject and role validation. It cannot manufacture an identity the
verifier would have rejected.

The end-to-end tests required by ADR-0063 section 4a exist precisely because
this factory stands in for the real path: the factory proves the database
boundary, the end-to-end tests prove the boundary it stands in for.
"""

from __future__ import annotations

from typing import Any

from .identity import AUTHENTICATED_ROLE, VerifiedIdentity, _build


def identity_for(subject: Any, role: str = AUTHENTICATED_ROLE) -> VerifiedIdentity:
    """Build a VerifiedIdentity for tests, with production-equivalent validation."""
    return _build(subject, role)
