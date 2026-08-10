"""Authentication errors.

One public failure type, deliberately. Distinguishing "bad signature" from
"expired" from "wrong issuer" to a caller turns the endpoint into a
token-validation oracle, and distinguishing "no such user" leaks account
existence. Callers get `AuthenticationError`; the specific reason is carried in
`reason` for server-side logging only and must never be returned to a client.
"""

from __future__ import annotations


class AuthenticationError(Exception):
    """A token could not be turned into a verified identity.

    `reason` is a short, non-sensitive category for logs. It never contains the
    token, a signature, a key, or any claim value.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ConfigurationError(Exception):
    """Trusted configuration is unusable. Raised at startup, not per request."""


class UnauthorizedIdentityConstruction(RuntimeError):
    """VerifiedIdentity was constructed outside the sanctioned path.

    See ADR-0063 section 4: this is a runtime guard against accidental misuse,
    not a proof of unforgeability. Python has no private constructor.
    """
