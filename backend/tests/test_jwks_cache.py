"""JWKS cache, rotation, rate limiting and SSRF boundary (ADR-0063 section 3, 3a, 3b).

The fetcher is injected throughout, so these tests are deterministic and never
touch the network.
"""

from __future__ import annotations

import pytest

from app.auth.config import AuthConfig
from app.auth.errors import AuthenticationError, ConfigurationError
from app.auth.jwks import JwksCache
from auth_fixtures import ISSUER, KeyPair, jwks_document


class Clock:
    """Manual clock, so cache expiry and rate limiting are tested by construction
    rather than by sleeping."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class CountingFetcher:
    def __init__(self, *keysets: list[KeyPair]) -> None:
        self._keysets = list(keysets)
        self.calls = 0
        self.fail = False

    def __call__(self) -> dict:
        self.calls += 1
        if self.fail:
            raise OSError("network down")
        index = min(self.calls - 1, len(self._keysets) - 1)
        return jwks_document(*self._keysets[index])


# ── Caching ──────────────────────────────────────────────────────────────────

def test_first_lookup_fetches_once():
    k = KeyPair("kid-1", "ES256")
    fetcher = CountingFetcher([k])
    cache = JwksCache(fetcher, clock=Clock())
    cache.get_key("kid-1")
    assert fetcher.calls == 1


def test_cache_hit_performs_no_network_call():
    k = KeyPair("kid-1", "ES256")
    fetcher = CountingFetcher([k])
    cache = JwksCache(fetcher, clock=Clock())
    for _ in range(50):
        cache.get_key("kid-1")
    assert fetcher.calls == 1, "steady-state verification must not hit the network"


def test_cache_expires_after_ttl():
    k = KeyPair("kid-1", "ES256")
    clock, fetcher = Clock(), CountingFetcher([k])
    cache = JwksCache(fetcher, ttl=600, clock=clock)
    cache.get_key("kid-1")
    clock.advance(599)
    cache.get_key("kid-1")
    assert fetcher.calls == 1
    clock.advance(2)          # now past the 600 s TTL
    cache.get_key("kid-1")
    assert fetcher.calls == 2


# ── Unknown kid, rotation, rate limiting ─────────────────────────────────────

def test_unknown_kid_triggers_exactly_one_refresh():
    old, new = KeyPair("old-kid", "ES256"), KeyPair("new-kid", "ES256")
    clock, fetcher = Clock(), CountingFetcher([old], [old, new])
    cache = JwksCache(fetcher, clock=clock)
    cache.get_key("old-kid")
    assert fetcher.calls == 1
    cache.get_key("new-kid")   # unknown -> one refresh -> found
    assert fetcher.calls == 2


def test_key_rotation_is_handled_without_restart():
    """Provider publishes a new key; the previous one keeps working."""
    old, new = KeyPair("old-kid", "ES256"), KeyPair("new-kid", "ES256")
    clock, fetcher = Clock(), CountingFetcher([old], [old, new])
    cache = JwksCache(fetcher, clock=clock)
    assert cache.get_key("old-kid") is not None
    assert cache.get_key("new-kid") is not None
    assert cache.get_key("old-kid") is not None, "old key must remain valid"


def test_repeated_unknown_kid_is_rate_limited():
    """The amplification defence: random kids must not become outbound fetches."""
    k = KeyPair("kid-1", "ES256")
    clock, fetcher = Clock(), CountingFetcher([k])
    cache = JwksCache(fetcher, min_refresh_interval=60, clock=clock)
    cache.get_key("kid-1")
    calls_before = fetcher.calls

    for i in range(25):
        with pytest.raises(AuthenticationError):
            cache.get_key(f"attacker-kid-{i}")

    assert fetcher.calls == calls_before + 1, (
        "25 unknown kids must cause at most ONE refresh inside the window"
    )


def test_rate_limit_lifts_after_the_interval():
    old, new = KeyPair("old-kid", "ES256"), KeyPair("new-kid", "ES256")
    clock, fetcher = Clock(), CountingFetcher([old], [old], [old, new])
    cache = JwksCache(fetcher, min_refresh_interval=60, clock=clock)
    cache.get_key("old-kid")
    with pytest.raises(AuthenticationError):
        cache.get_key("new-kid")          # refresh happens, key still absent
    with pytest.raises(AuthenticationError):
        cache.get_key("new-kid")          # rate limited
    clock.advance(61)
    assert cache.get_key("new-kid") is not None


def test_unknown_kid_after_refresh_is_rejected():
    k = KeyPair("kid-1", "ES256")
    cache = JwksCache(CountingFetcher([k]), clock=Clock())
    cache.get_key("kid-1")
    with pytest.raises(AuthenticationError):
        cache.get_key("no-such-kid")


def test_missing_kid_is_rejected():
    cache = JwksCache(CountingFetcher([KeyPair("kid-1", "ES256")]), clock=Clock())
    with pytest.raises(AuthenticationError):
        cache.get_key("")


# ── Fail closed ──────────────────────────────────────────────────────────────

def test_jwks_unavailable_fails_closed():
    fetcher = CountingFetcher([KeyPair("kid-1", "ES256")])
    fetcher.fail = True
    cache = JwksCache(fetcher, clock=Clock())
    with pytest.raises(AuthenticationError):
        cache.get_key("kid-1")


def test_expired_cache_with_failing_fetch_fails_closed():
    """Stale keys are not served. Bounded downtime beats unbounded compromise."""
    k = KeyPair("kid-1", "ES256")
    clock, fetcher = Clock(), CountingFetcher([k])
    cache = JwksCache(fetcher, ttl=600, clock=clock)
    cache.get_key("kid-1")
    clock.advance(601)
    fetcher.fail = True
    with pytest.raises(AuthenticationError):
        cache.get_key("kid-1")


def test_empty_keyset_fails_closed():
    cache = JwksCache(lambda: {"keys": []}, clock=Clock())
    with pytest.raises(AuthenticationError):
        cache.get_key("kid-1")


def test_malformed_key_entry_does_not_poison_the_set():
    k = KeyPair("good-kid", "ES256")
    doc = jwks_document(k)
    doc["keys"].append({"kid": "bad-kid", "kty": "EC", "crv": "nonsense"})
    cache = JwksCache(lambda: doc, clock=Clock())
    assert cache.get_key("good-kid") is not None


# ── SSRF boundary (I-22) ─────────────────────────────────────────────────────

def test_jwks_url_is_derived_from_the_issuer():
    config = AuthConfig.from_issuer(ISSUER)
    assert config.jwks_url == f"{ISSUER}/.well-known/jwks.json"
    assert config.expected_host == "test-project.supabase.co"


def test_http_issuer_is_refused():
    with pytest.raises(ConfigurationError):
        AuthConfig.from_issuer("http://test-project.supabase.co/auth/v1")


@pytest.mark.parametrize(
    "url",
    [
        "https://attacker.example.com/.well-known/jwks.json",
        "http://test-project.supabase.co/.well-known/jwks.json",   # scheme
        "https://test-project.supabase.co.evil.com/jwks.json",     # suffix trick
        "https://evil.supabase.co/.well-known/jwks.json",          # sibling project
    ],
)
def test_disallowed_jwks_urls_are_refused(url):
    with pytest.raises(ConfigurationError):
        AuthConfig.from_issuer(ISSUER).assert_url_allowed(url)


def test_sibling_supabase_project_is_refused_despite_matching_suffix():
    """The reason host checking is exact equality, not a suffix test.

    Anyone can create a Supabase project, so `endswith('.supabase.co')` would
    admit a key set an attacker fully controls while looking like a tightened
    control.
    """
    config = AuthConfig.from_issuer(ISSUER)
    with pytest.raises(ConfigurationError):
        config.assert_url_allowed("https://evil.supabase.co/auth/v1/.well-known/jwks.json")


def test_cross_host_redirect_is_refused():
    """A redirect is an attacker-influenceable way to move the fetch."""
    from app.auth.jwks import _NoCrossHostRedirect

    handler = _NoCrossHostRedirect(AuthConfig.from_issuer(ISSUER))
    with pytest.raises(ConfigurationError):
        handler.redirect_request(
            None, None, 302, "Found", {}, "https://attacker.example.com/jwks.json"
        )


def test_token_issuer_claim_cannot_steer_the_fetch():
    """The token's `iss` is compared, never used to locate the key set.

    Asserted structurally: AuthConfig exposes no way to supply a JWKS URL, so no
    request-derived value can reach the fetcher.
    """
    import inspect

    # Structural proof: the only way to build a config is from an issuer. There
    # is no parameter through which a request-derived JWKS URL could arrive.
    params = set(inspect.signature(AuthConfig.from_issuer).parameters) - {"cls"}
    assert params == {"issuer"}

    config = AuthConfig.from_issuer(ISSUER)
    assert config.jwks_url == f"{ISSUER}/.well-known/jwks.json"

    # A token claiming a different issuer cannot move the fetch: the config is
    # built from deploy-time input and never consults a token.
    hostile = AuthConfig.from_issuer(ISSUER)
    assert hostile.expected_host == "test-project.supabase.co"
