"""HTTP authentication boundary (ADR-0064).

Thin by design: parse the Bearer envelope, delegate to the slice 2 verifier,
hand the resulting VerifiedIdentity to the handler. No JWT parsing, no database
credential, no second trust path.
"""

from .app import create_app
from .dependencies import require_identity
from .errors import AuthenticationRequired

__all__ = ["AuthenticationRequired", "create_app", "require_identity"]
