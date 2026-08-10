"""VerifiedIdentity construction boundary and claim minimisation.

Covers ADR-0063 I-19 (construction), I-20 (minimisation) and I-23 (test factory
containment). The claim-minimisation tests that touch PostgreSQL live in
test_auth_end_to_end.py; these assert the payload the session layer will send.
"""

from __future__ import annotations

import json
import uuid

import pytest

from app.auth.errors import UnauthorizedIdentityConstruction
from app.auth.identity import VerifiedIdentity
from app.auth.testing import identity_for


# ── Construction boundary (I-19) ─────────────────────────────────────────────

def test_direct_construction_is_refused():
    with pytest.raises(UnauthorizedIdentityConstruction):
        VerifiedIdentity(uuid.uuid4(), "authenticated")


def test_direct_construction_with_a_wrong_sentinel_is_refused():
    with pytest.raises(UnauthorizedIdentityConstruction):
        VerifiedIdentity(uuid.uuid4(), "authenticated", _sentinel=object())


def test_the_boundary_is_documented_as_defeatable_not_absolute():
    """ADR-0063 section 4 is explicit that this is defence in depth, not proof.

    Reaching the module-private sentinel is possible; the static governance
    check is what stops a deliberate bypass reaching main. This test pins that
    honesty in place so nobody later reads the type as unforgeable.
    """
    from app.auth import identity as identity_module

    sentinel = identity_module._CONSTRUCTION_SENTINEL
    forged = VerifiedIdentity(uuid.uuid4(), "authenticated", _sentinel=sentinel)
    assert isinstance(forged, VerifiedIdentity), (
        "the runtime guard is bypassable by design; the governance check is the "
        "control that stops this reaching main"
    )


def test_identity_is_immutable():
    identity = identity_for(uuid.uuid4())
    with pytest.raises(AttributeError):
        identity._subject = uuid.uuid4()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        del identity._role  # type: ignore[misc]


def test_repr_does_not_leak_the_subject():
    """Identities appear in tracebacks and logs; the subject is a user id."""
    subject = uuid.uuid4()
    text = repr(identity_for(subject))
    assert str(subject) not in text
    assert "redacted" in text


# ── The test factory applies production validation (section 4a) ──────────────

def test_factory_returns_the_same_type_the_db_layer_consumes():
    assert isinstance(identity_for(uuid.uuid4()), VerifiedIdentity)


@pytest.mark.parametrize("bad", ["not-a-uuid", "", None, 42, "12345"])
def test_factory_rejects_subjects_the_verifier_would_reject(bad):
    """The factory must not be a second, laxer construction path."""
    with pytest.raises(UnauthorizedIdentityConstruction):
        identity_for(bad)


def test_factory_rejects_non_authenticated_roles():
    with pytest.raises(UnauthorizedIdentityConstruction):
        identity_for(uuid.uuid4(), role="anon")


def test_factory_accepts_a_uuid_string_and_normalises_it():
    subject = uuid.uuid4()
    assert identity_for(str(subject)).subject == subject


# ── Claim minimisation (I-20) ────────────────────────────────────────────────

HIGH_CLASS_CLAIMS = ("email", "phone", "user_metadata", "app_metadata",
                     "session_id", "aal", "amr", "is_anonymous")


def test_database_claims_contains_only_sub_and_role():
    identity = identity_for(uuid.uuid4())
    assert set(identity.database_claims()) == {"sub", "role"}


def test_database_claims_excludes_every_high_class_claim():
    payload = identity_for(uuid.uuid4()).database_claims()
    for claim in HIGH_CLASS_CLAIMS:
        assert claim not in payload, f"{claim} must never reach PostgreSQL"


def test_serialised_payload_carries_no_pii():
    """The exact string handed to set_config, checked as text.

    A structural assertion could pass while a nested value still serialised
    something sensitive, so this asserts on the wire format.
    """
    serialised = json.dumps(identity_for(uuid.uuid4()).database_claims())
    for needle in ("email", "phone", "metadata", "@", "session"):
        assert needle not in serialised


def test_identity_carries_no_attribute_holding_pii():
    """Nothing can be minimised out later if it was never carried."""
    identity = identity_for(uuid.uuid4())
    for claim in HIGH_CLASS_CLAIMS:
        assert not hasattr(identity, claim)


# ── The auth package holds no database dependency (I-21) ─────────────────────

def test_auth_package_imports_no_database_driver():
    """Asserted at runtime as well as statically, because the governance check
    can be deleted and this cannot be without a visible test failure."""
    import importlib
    import sys

    for name in ("app.auth", "app.auth.verifier", "app.auth.jwks",
                 "app.auth.identity", "app.auth.config", "app.auth.testing"):
        importlib.import_module(name)

    forbidden = {"psycopg", "psycopg_pool", "sqlalchemy", "asyncpg", "supabase"}
    for module_name in list(sys.modules):
        if module_name.startswith("app.auth"):
            module = sys.modules[module_name]
            imported = {
                getattr(value, "__module__", "").split(".")[0]
                for value in vars(module).values()
                if hasattr(value, "__module__")
            }
            assert not (imported & forbidden), (
                f"{module_name} pulled in a database client: {imported & forbidden}"
            )
