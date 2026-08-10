"""JWKS retrieval and cache (ADR-0063 section 3, 3a, 3b).

Why this exists rather than PyJWKClient
---------------------------------------
PyJWKClient was inspected empirically before this module was written:

    lifespan default        300 s   (ADR-0063 requires 600 s)
    refetch on unknown kid  yes
    rate limiting           NONE

The missing rate limit is the disqualifying gap. Without it, an attacker
sending random `kid` values turns every request into an outbound fetch --
free amplification against the provider and a self-inflicted outage. PyJWT is
still used for what it does well: parsing a JWK into a verification key.

Scope, stated plainly (ADR-0063 section 3b)
-------------------------------------------
This cache is IN-MEMORY and PER-PROCESS. With N worker processes there are N
caches and the effective bound is N refreshes per 60 s, not one. That is
accepted residual risk at MVP scale (threat J19) and is NOT a global guarantee.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from jwt import PyJWK

from .config import AuthConfig
from .errors import AuthenticationError, ConfigurationError

CACHE_TTL_SECONDS = 600          # matches the provider's own cache-control
MIN_REFRESH_INTERVAL_SECONDS = 60  # unknown-kid refresh rate limit, per process
FETCH_TIMEOUT_SECONDS = 5


class _NoCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """Permit redirects only within the configured host.

    A redirect is an attacker-influenceable way to move the fetch somewhere
    else, so it is checked with the same exact-host rule as the initial URL.
    """

    def __init__(self, config: AuthConfig) -> None:
        self._config = config

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        self._config.assert_url_allowed(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def http_fetcher(config: AuthConfig) -> Callable[[], dict[str, Any]]:
    """Real network fetcher. Injected, so tests never touch the network."""

    def fetch() -> dict[str, Any]:
        config.assert_url_allowed(config.jwks_url)
        opener = urllib.request.build_opener(_NoCrossHostRedirect(config))
        with opener.open(config.jwks_url, timeout=FETCH_TIMEOUT_SECONDS) as response:
            return json.loads(response.read())

    return fetch


class JwksCache:
    """Bounded, fail-closed JWKS cache."""

    def __init__(
        self,
        fetcher: Callable[[], dict[str, Any]],
        *,
        ttl: int = CACHE_TTL_SECONDS,
        min_refresh_interval: int = MIN_REFRESH_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetcher
        self._ttl = ttl
        self._min_refresh_interval = min_refresh_interval
        self._clock = clock
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at: float | None = None
        # Rate limiting applies ONLY to unknown-kid refreshes. A TTL refresh is
        # scheduled, not attacker-triggered, so counting it here would arm the
        # limiter against the very next legitimate rotation -- blocking a new
        # kid for 60 s after every routine cache refill. Caught by
        # test_unknown_kid_triggers_exactly_one_refresh.
        self._last_unknown_kid_refresh: float | None = None
        # Observability for tests and operators. Never contains key material.
        self.fetch_count = 0

    # -- internals ------------------------------------------------------------
    def _expired(self) -> bool:
        return self._fetched_at is None or (self._clock() - self._fetched_at) >= self._ttl

    def _refresh(self) -> None:
        """Fetch and replace the key set. Raises on any failure (fail closed)."""
        try:
            document = self._fetch()
        except (urllib.error.URLError, OSError, ValueError, ConfigurationError) as exc:
            # Never serve a stale or unverified key on failure.
            raise AuthenticationError("jwks_unavailable") from exc

        keys: dict[str, PyJWK] = {}
        for entry in document.get("keys", []):
            kid = entry.get("kid")
            if not kid:
                continue
            try:
                keys[kid] = PyJWK(entry)
            except Exception:  # noqa: BLE001 - a malformed key must not poison the set
                continue

        if not keys:
            raise AuthenticationError("jwks_empty")

        self._keys = keys
        self._fetched_at = self._clock()
        self.fetch_count += 1

    def _rate_limited(self) -> bool:
        if self._last_unknown_kid_refresh is None:
            return False
        return (
            self._clock() - self._last_unknown_kid_refresh
        ) < self._min_refresh_interval

    # -- public ---------------------------------------------------------------
    def get_key(self, kid: str) -> PyJWK:
        """Return the verification key for `kid`, or fail closed.

        Order matters: a normal request hits the cache and performs no network
        call at all.
        """
        if not kid:
            raise AuthenticationError("missing_kid")

        if self._expired():
            self._refresh()

        key = self._keys.get(kid)
        if key is not None:
            return key

        # Unknown kid. This is the rotation path -- and also the abuse path, so
        # it gets at most one refresh, rate limited.
        if self._rate_limited():
            raise AuthenticationError("unknown_kid_rate_limited")

        # Record the attempt before fetching, so a failing fetch still consumes
        # the window. Otherwise a hostile kid whose fetch errors could be
        # retried without limit.
        self._last_unknown_kid_refresh = self._clock()
        self._refresh()

        key = self._keys.get(kid)
        if key is None:
            raise AuthenticationError("unknown_kid")
        return key
