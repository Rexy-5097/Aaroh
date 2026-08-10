"""Aaroh authentication boundary (ADR-0063).

    token -> JwtVerifier -> VerifiedIdentity -> db.request_transaction -> RLS

This package holds NO database credential and opens NO connection (I-21). The
dependency direction is one-way: `auth` produces an identity, `db` consumes it.

`testing` is deliberately NOT re-exported here -- production code must not
import it (I-23).
"""

from .config import AuthConfig
from .errors import (
    AuthenticationError,
    ConfigurationError,
    UnauthorizedIdentityConstruction,
)
from .identity import AUTHENTICATED_ROLE, VerifiedIdentity
from .jwks import JwksCache, http_fetcher
from .verifier import ALLOWED_ALGORITHMS, CLOCK_SKEW_SECONDS, JwtVerifier

__all__ = [
    "ALLOWED_ALGORITHMS",
    "AUTHENTICATED_ROLE",
    "AuthConfig",
    "AuthenticationError",
    "CLOCK_SKEW_SECONDS",
    "ConfigurationError",
    "JwksCache",
    "JwtVerifier",
    "UnauthorizedIdentityConstruction",
    "VerifiedIdentity",
    "http_fetcher",
]
