"""HTTP error responses for the authentication boundary (ADR-0064 section 1, 5).

Every authentication failure produces the SAME response. The reason is recorded
against a correlation id server-side and never returned: distinguishing
"malformed" from "bad signature" from "expired" turns the endpoint into a
token-validation oracle, and distinguishing "no such user" leaks account
existence.
"""

from __future__ import annotations

from typing import Any

# The single public authentication failure. Fixed strings -- never built from a
# token, a claim, or the reason a verification failed (I-24, I-27).
AUTH_PROBLEM_TYPE = "https://aaroh.app/errors/authentication-required"
AUTH_PROBLEM_TITLE = "Authentication Required"
AUTH_PROBLEM_DETAIL = "A valid bearer token is required."

# RFC 6750 permits WWW-Authenticate: Bearer error="invalid_token". It is
# deliberately omitted: it would distinguish MISSING credentials from REJECTED
# ones, reintroducing at the header level exactly the discrimination the body
# avoids.
WWW_AUTHENTICATE = "Bearer"

PROBLEM_MEDIA_TYPE = "application/problem+json"


class AuthenticationRequired(Exception):
    """Raised by the dependency; rendered by the handler registered on the app.

    `reason` is a short non-sensitive category for server-side logs. It is NOT
    part of the response and must never contain a token or a claim value.
    """

    def __init__(self, reason: str = "unauthenticated") -> None:
        super().__init__(reason)
        self.reason = reason


def authentication_problem(correlation_id: str) -> dict[str, Any]:
    """RFC 7807 body (standards/api_design.md).

    `instance` is deliberately absent. It would echo the request path --
    client-controlled input reflected into a response -- and adds nothing to a
    failure that is already uniform.
    """
    return {
        "type": AUTH_PROBLEM_TYPE,
        "title": AUTH_PROBLEM_TITLE,
        "status": 401,
        "detail": AUTH_PROBLEM_DETAIL,
        "correlation_id": correlation_id,
    }
