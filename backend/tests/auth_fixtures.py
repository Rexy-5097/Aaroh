"""Local cryptographic fixtures for the authentication tests.

All keys are generated in-process for the test run. No production key material
is used, and nothing here touches the network or the live Supabase project.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa

ISSUER = "https://test-project.supabase.co/auth/v1"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
AUDIENCE = "authenticated"


class KeyPair:
    """A signing key plus its public JWK, addressed by kid."""

    def __init__(self, kid: str, alg: str) -> None:
        self.kid = kid
        self.alg = alg
        if alg == "ES256":
            self.private = ec.generate_private_key(ec.SECP256R1())
        elif alg == "RS256":
            self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        else:  # pragma: no cover - guarded by callers
            raise ValueError(alg)
        self.public = self.private.public_key()

    def jwk(self) -> dict[str, Any]:
        entry = jwt.algorithms.get_default_algorithms()[self.alg].to_jwk(
            self.public, as_dict=True
        )
        entry.update({"kid": self.kid, "use": "sig", "alg": self.alg})
        return entry

    def public_pem(self) -> bytes:
        from cryptography.hazmat.primitives import serialization

        return self.public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def sign(self, claims: dict[str, Any], *, headers: dict[str, Any] | None = None) -> str:
        head = {"kid": self.kid}
        head.update(headers or {})
        return jwt.encode(claims, self.private, algorithm=self.alg, headers=head)


def jwks_document(*pairs: KeyPair) -> dict[str, Any]:
    return {"keys": [p.jwk() for p in pairs]}


def valid_claims(**overrides: Any) -> dict[str, Any]:
    """A claim set shaped like the one observed live on aaroh-dev.

    Includes the High-class claims a real Supabase token carries, so the
    minimisation tests are exercised against a realistic payload rather than a
    convenient one.
    """
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": str(uuid.uuid4()),
        "role": "authenticated",
        "iat": now,
        "exp": now + 3600,
        "aal": "aal1",
        "session_id": str(uuid.uuid4()),
        "is_anonymous": False,
        "email": "someone@example.invalid",
        "phone": "+10000000000",
        "user_metadata": {"full_name": "Test Person"},
        "app_metadata": {"provider": "email"},
    }
    claims.update(overrides)
    return claims
