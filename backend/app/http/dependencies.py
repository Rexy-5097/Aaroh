"""The authentication dependency (ADR-0064 section 3).

This module is the ONLY route from an HTTP request to a VerifiedIdentity.

It performs no JWT parsing or verification of its own (I-26): it parses the
Bearer envelope and hands the token to the verifier built in slice 2. A second
verification path here -- even "just to read the user id" -- is the exact defect
this boundary exists to prevent.

It holds no pool and opens no connection (I-28). Authentication is a
cryptographic operation against a cached key set; it needs no database.
"""

from __future__ import annotations

from fastapi import Depends, Request

from app.auth.errors import AuthenticationError
from app.auth.identity import VerifiedIdentity
from app.auth.verifier import JwtVerifier

from .errors import AuthenticationRequired

BEARER_SCHEME = "bearer"


def _extract_bearer(header_value: str | None) -> str:
    """Strict RFC 6750 parse. Every deviation raises the same error.

    Deliberately strict: exactly two whitespace-separated parts and a
    case-insensitive `Bearer` scheme. Tolerating extra parts would mean guessing
    at caller intent on a security boundary, and every tolerated shape is a case
    somebody must later reason about.

    `str.split()` collapses runs of whitespace and never yields an empty part,
    so an empty token cannot reach the scheme check -- "Bearer " splits to a
    single element and is rejected by the arity check above. An explicit
    `if not token` guard was removed after mutation testing showed it was
    unreachable: it read as a control while being incapable of firing, which is
    worse than no code at all because a reader trusts it.

    RFC 7235 allows 1*SP between scheme and credentials, so whitespace-collapsing
    `split()` is used rather than `split(" ")` -- the latter would reject the
    legal `Bearer  token`.
    """
    if not header_value:
        raise AuthenticationRequired("missing_authorization_header")

    parts = header_value.split()
    if len(parts) != 2:
        raise AuthenticationRequired("malformed_authorization_header")

    scheme, token = parts
    if scheme.lower() != BEARER_SCHEME:
        raise AuthenticationRequired("unsupported_scheme")
    return token


def get_verifier(request: Request) -> JwtVerifier:
    """The process-wide verifier, built once at startup and stored on the app.

    Built once because the JWKS cache it owns is process-scoped by design
    (ADR-0063 section 3b). Rebuilding per request would discard the cache and
    turn every request into a network fetch.
    """
    verifier = getattr(request.app.state, "verifier", None)
    if verifier is None:  # pragma: no cover - configuration error, not a request path
        raise RuntimeError("no verifier configured on the application")
    return verifier


def require_identity(
    request: Request, verifier: JwtVerifier = Depends(get_verifier)
) -> VerifiedIdentity:
    """Resolve the caller's verified identity, or refuse the request.

    Returns a VerifiedIdentity or raises. There is no third outcome and no
    anonymous identity object -- a handler cannot accidentally proceed with a
    partially-trusted caller.

    FastAPI resolves dependencies before the handler body, so a failure here
    means the handler never executes (I-25). That is a property of the
    framework's execution order and is tested rather than assumed.
    """
    token = _extract_bearer(request.headers.get("authorization"))
    try:
        return verifier.verify(token)
    except AuthenticationError as exc:
        # The verifier's reason is carried for server-side logging only. It is
        # never returned: the response is identical for every failure (I-24).
        raise AuthenticationRequired(exc.reason) from None
