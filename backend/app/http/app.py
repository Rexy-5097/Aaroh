"""Application factory and the boundary probe route (ADR-0064).

SCOPE: this is the authentication boundary, not an API. The single route below
exists so the boundary can be tested end to end. It is not a product endpoint
and is expected to be replaced when real routes arrive.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth.identity import VerifiedIdentity
from app.auth.verifier import JwtVerifier
from app.db.session import request_transaction

from .dependencies import require_identity
from .errors import (
    PROBLEM_MEDIA_TYPE,
    WWW_AUTHENTICATE,
    AuthenticationRequired,
    authentication_problem,
)

CORRELATION_HEADER = "X-Request-ID"


def create_app(verifier: JwtVerifier, pool=None) -> FastAPI:
    """Build the application.

    The verifier and pool are injected rather than constructed here: the HTTP
    layer owns neither the JWKS cache nor a database credential (I-28).
    """
    app = FastAPI(title="Aaroh authentication boundary", docs_url=None, redoc_url=None)
    app.state.verifier = verifier
    app.state.pool = pool

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):
        """Server-generated correlation id.

        A client-supplied X-Request-ID is IGNORED, not echoed. Accepting it
        would let a caller inject arbitrary text into logs and into a response
        body that some client will render (ADR-0064 section 5).
        """
        request.state.correlation_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers[CORRELATION_HEADER] = request.state.correlation_id
        return response

    @app.exception_handler(AuthenticationRequired)
    async def _unauthenticated(request: Request, exc: AuthenticationRequired):
        """One response for every authentication failure (I-24).

        `exc.reason` is intentionally NOT used here. It exists for server-side
        logging; putting it in the response would rebuild the oracle.
        """
        correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
        return JSONResponse(
            status_code=401,
            content=authentication_problem(correlation_id),
            media_type=PROBLEM_MEDIA_TYPE,
            headers={
                "WWW-Authenticate": WWW_AUTHENTICATE,
                CORRELATION_HEADER: correlation_id,
            },
        )

    @app.get("/internal/boundary-probe")
    def boundary_probe(identity: VerifiedIdentity = Depends(require_identity)):
        """Boundary probe -- NOT a product endpoint.

        Proves the whole chain in one request: an authenticated caller reaches
        the database through the sanctioned session and sees only their own
        rows. It returns a count rather than data, so it discloses nothing the
        caller could not already read.
        """
        pool = app.state.pool
        visible = None
        if pool is not None:
            with request_transaction(pool, identity) as conn:
                visible = conn.execute("SELECT count(*) FROM public.profiles").fetchone()[0]
        return {"subject": str(identity.subject), "visible_rows": visible}

    return app
