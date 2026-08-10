---
id: ART-ADR-0064
title: "HTTP Authentication Boundary"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-10
modified: 2026-08-10
related_adr: ADR-0063
related_standard: standards/api_design.md
related_checklist: QG-005
related_workflow: master.md
related_agent: security-reviewer
---

# Architecture Decision Record: ADR-0064

> **Status:** Accepted | **Date:** 2026-08-10 | **Decider:** Rexy-5097

## Context

`ADR-0061` and `ADR-0063` built a complete identity chain and proved it end to end:

```
token -> verifier -> VerifiedIdentity -> request_transaction -> SET LOCAL -> RLS
```

Every link is tested and mutation-verified. But nothing calls it. The verifier has no caller, so an HTTP request has no defined route into the chain — and the moment one exists, it becomes the place where a second trust path could appear.

The failure this ADR exists to prevent is specific and common: a route that reads the `Authorization` header itself, decodes the token for "just the user id", and proceeds. That produces two verification paths, one of them wrong, and the wrong one wins because it is more convenient.

**Scope.** How an HTTP request reaches an already-verified identity, and what a client is told when it cannot. It defines no product endpoint, no resource, no schema. The single route introduced is a boundary probe that exists to be tested, not a feature.

## Problem Statement

How does an HTTP request obtain a `VerifiedIdentity` such that no protected operation can execute without passing through the existing verifier, and such that failure discloses nothing beyond "not authenticated"?

## Alternatives Considered

**Option A — Middleware that authenticates every request globally.** Rejected. Fail-open by construction: a route added to a path the middleware does not match is silently unauthenticated, and the mistake is invisible in the route's own code. Authentication should be visible where the route is declared.

**Option B — Each route parses the `Authorization` header itself.** Rejected outright. This is the second trust path described above.

**Option C — A FastAPI dependency returning `VerifiedIdentity`, declared per protected route.** **Accepted.** The dependency is visible in the handler signature, the handler receives a type it cannot construct, and a route without it cannot obtain an identity at all.

**Option D — Middleware for authentication plus a dependency for injection.** Rejected as redundant: two mechanisms, one of which can silently disagree with the other about which paths are protected.

## Decision

### 1. Failure semantics — every authentication failure is the same 401

| Condition | Status | Body |
|-----------|--------|------|
| No `Authorization` header | 401 | identical |
| Header present but malformed | 401 | identical |
| Wrong scheme (`Basic`, `Token`, …) | 401 | identical |
| Empty bearer token | 401 | identical |
| Malformed JWT | 401 | identical |
| Invalid signature | 401 | identical |
| Expired | 401 | identical |
| Wrong issuer or audience | 401 | identical |
| Rejected role, anonymous identity | 401 | identical |
| JWKS unavailable | 401 | identical |

**All of these collapse to one response**: `401`, `WWW-Authenticate: Bearer`, and an RFC 7807 body whose `detail` is a fixed string. This follows `ADR-0063` section 7 — discriminating between "malformed" and "invalid signature" and "expired" turns the endpoint into a token-validation oracle, and distinguishing "no such user" leaks account existence.

The specific reason is recorded server-side against a correlation id. **It is never returned.**

`WWW-Authenticate` carries the bare scheme. RFC 6750 permits an `error="invalid_token"` parameter, and it is deliberately omitted: it would distinguish *missing* credentials from *rejected* ones, reintroducing at the header level the discrimination the body avoids.

### 2. Authorization is a different question with different answers

Per `ADR-0061` section 5, authentication and authorization are separate, and authorization itself has two layers:

| Situation | Status | Why |
|-----------|--------|-----|
| Not authenticated | **401** | The caller may retry with credentials |
| Authenticated, but the *operation* is not permitted — quota, entitlement, state-machine illegality | **403** | The caller is known; the action is refused. Reveals nothing about any resource |
| Authenticated, resource not visible to this caller | **404** | `ADR-0061` section 6: a 403 here confirms the object exists, making the status code an enumeration oracle |

The distinction is *what the answer reveals*. A 403 about an **action** discloses nothing — "you may not do this" is true regardless of what exists. A 403 about a **resource** discloses that the resource exists. Under RLS the second case is automatic: another user's row is simply not visible, so the handler finds nothing and returns 404 without any special logic.

**No operation-level authorization is implemented in this slice.** There are no operations to authorize. The 403 row above records the decision so the first quota or entitlement check has a rule to follow rather than inventing one.

### 3. The dependency is the only way in

A protected route declares the dependency and receives a `VerifiedIdentity`. Consequences, all of them deliberate:

- A route that does not declare it **cannot obtain an identity**, because `VerifiedIdentity` cannot be constructed outside the auth package (`ADR-0063` I-19).
- The handler receives the identity type, never raw claims and never the token. A handler cannot inspect a claim it was never given.
- FastAPI resolves dependencies **before** the handler body. Authentication failure raises, so the handler never executes — this is a property of the framework's execution order, and it is tested rather than assumed.
- The dependency returns `VerifiedIdentity` or raises. There is no third outcome and no "anonymous identity" object.

**Dependency caching.** FastAPI caches dependency results within a single request. That is the desired behaviour — one verification per request — and it does not persist across requests. Because the consequence of being wrong is identity reuse between callers, it is tested explicitly rather than trusted.

### 4. The HTTP layer holds no database credential

The authentication dependency performs **no database access**. It has no pool, opens no connection, and issues no query — authentication is a cryptographic operation against a cached key set.

Routes that need data receive the pool from application state and pass the identity to the existing `request_transaction`. The HTTP layer therefore adds no new database path: `ADR-0061` I-12 continues to hold, and the existing governance check already covers `backend/app/http/` because it is inside the scanned roots and is not the `db/` layer.

**Sync, not async.** The dependency is a synchronous function, matching the sync `psycopg` choice in slice 1. FastAPI runs sync dependencies in a threadpool, so the blocking JWKS fetch on a cache miss does not stall the event loop. Mixing a sync database layer with an async auth layer would create exactly the kind of subtle mismatch that produces connection leaks under load.

### 5. Tokens and headers never appear in logs or responses

- The raw token, the `Authorization` header, and any signature are **never** logged, never placed in an exception message, and never returned in a response body.
- The RFC 7807 body for a 401 omits `instance`. Echoing the request path reflects client-controlled input into a response, and the path adds nothing to a failure that is already generic.
- `detail` is a fixed constant. It is not built from the token, the claims, or the failure reason.

**Correlation ids** are generated **server-side** as a UUID4 per request, returned in the body and in an `X-Request-ID` response header, and used to tie a client report to a server-side log entry. A client-supplied `X-Request-ID` is **ignored, not echoed** — accepting it would let a caller inject arbitrary text into logs and into a response body that some client will render.

### 6. Rate limiting is deferred, with reasoning

Rate limiting is **not** implemented in this slice, and this is a decision rather than an omission.

It requires its own decisions — per-IP or per-subject, where counters live, and how that interacts with the per-process constraint recorded in `ADR-0063` section 3b — and those belong with the first route that has a real cost to protect.

What is already bounded: an unauthenticated request performs no database work, and JWKS refresh is rate limited per process (`ADR-0063`), so the expensive path an attacker might target is already capped. The cheap path — repeated invalid tokens — costs a signature verification against a cached key.

`standards/security.md` requires rate limiting before production, and `ADR-0063` J15 already notes the cost dimension. This slice inherits that obligation; it does not discharge it.

## Security Invariants

Extends `ADR-0061` and `ADR-0063`:

| ID | Invariant |
|----|-----------|
| **I-24** | Every authentication failure returns 401 with an identical body. No status, header, or message distinguishes *why*. |
| **I-25** | A protected operation cannot execute unless the authentication dependency resolved successfully. |
| **I-26** | The HTTP layer performs no JWT parsing or verification of its own. It calls the existing verifier and nothing else. |
| **I-27** | The `Authorization` header, the bearer token, and any part of it never appear in a log, an exception message, or a response body. |
| **I-28** | The authentication dependency opens no database connection and holds no pool. |
| **I-29** | Handlers receive `VerifiedIdentity`. Raw claims and raw tokens never reach handler code. |

## Data-Flow Boundary

```
 HTTP request
   Authorization: Bearer <token>
        │
        ▼
 ┌──────────────────────────────────────────────┐
 │ http/  (no database credential, I-28)        │
 │  1. strict Bearer parse -- any deviation     │
 │     yields the SAME 401            (I-24)    │
 │  2. delegate to the EXISTING verifier (I-26) │
 │     -- no second parse, no decode            │
 │  3. return VerifiedIdentity, or raise        │
 └───────────────────┬──────────────────────────┘
                     │  VerifiedIdentity  (never claims, never the token)
                     ▼
              route handler  (I-25, I-29)
                     │
                     ▼
        db.request_transaction(pool, identity)
                     │
                     ▼
              SET LOCAL -> RLS -> caller-owned rows
```

## Threat Model

| # | Threat | Mitigation | Residual |
|---|--------|-----------|----------|
| H1 | Route reads the header and decodes the token itself, creating a second trust path | Handlers receive only `VerifiedIdentity`; governance forbids JWT decoding outside the auth package (I-26) | Low |
| H2 | Route forgets authentication and runs unauthenticated | It cannot obtain an identity — the type is unconstructable outside auth (`ADR-0063` I-19); governance requires the dependency on any handler using `request_transaction` | Low |
| H3 | Error responses form a token-validation oracle | One status, one body, one `WWW-Authenticate` (I-24) | Low |
| H4 | 403-vs-404 confusion leaks resource existence | Action refusals are 403; resource invisibility is 404 (`ADR-0061` section 6) | Low |
| H5 | Token or header leaks into logs, exceptions, or a response | Never logged or interpolated; `instance` omitted; `detail` constant (I-27) | Moderate — a convention plus a governance check, not a runtime guarantee |
| H6 | Client-supplied correlation id injected into logs or a rendered response | Generated server-side; client value ignored | Low |
| H7 | Dependency caching reuses one caller's identity for another | FastAPI caches within a request only; tested explicitly | Low |
| H8 | Authentication dependency opens a connection, adding a database path | No pool, no connection (I-28); existing I-12 check covers the http package | Low |
| H9 | Unauthenticated flooding | No database work on the unauthenticated path; JWKS refresh already rate limited | **Accepted — rate limiting deferred, section 6** |
| H10 | Handler mutates or re-derives identity from request data | Identity is immutable and arrives only from the dependency (`ADR-0061` I-4) | Low |

## Failure Modes

| Failure | Cause | Detection | Recovery |
|---------|-------|-----------|---------|
| Unauthenticated access to a protected route | Dependency omitted | Governance check; route-level test | Add the dependency; audit access logs |
| Oracle via differing errors | A helpful error message added later | Identical-response tests across every failure mode | Restore the single response |
| Token in logs | A debug statement left in | Governance check; log-content test | Remove; treat as an incident and rotate if it reached storage |
| Identity reuse across requests | Dependency scope misunderstood | Cross-request identity test | Fix scoping; treat as an incident |
| Second verifier appears | A convenience decode added in a handler | Governance check (I-26) | Remove; route through the existing verifier |

## Testing Strategy

Minimum invariant coverage, not a target. Each invariant needs a test that catches its specific failure.

**Bearer parsing:** absent header · empty header · `Bearer` with no token · empty token · wrong scheme (`Basic`, `Token`, `bearer` casing) · extra segments · leading/trailing whitespace.

**Verification outcomes through HTTP:** valid token → 200 · malformed JWT · invalid signature · expired · wrong issuer · wrong audience · rejected role · anonymous identity · unknown `kid` — **every one asserted to produce a byte-identical 401 body and headers**.

**Boundary properties:** handler receives a `VerifiedIdentity`, not a dict or claims · handler does not execute on authentication failure · token and `Authorization` header absent from body, headers, and exception text · the dependency opens zero database connections · identity is not reused across requests.

**Integration (mandatory):** HTTP request with a locally signed token → dependency → `VerifiedIdentity` → `request_transaction` → RLS → **only caller-owned rows**, and a second caller sees only their own.

**Mutation testing** is mandatory, following slices 1 and 2. Each mutation must be caught by a *named* test: bypass verification · accept a malformed header · return raw claims · skip the dependency · construct `VerifiedIdentity` directly · execute the handler after failure · log the `Authorization` header · open a connection in the dependency · accept a non-Bearer scheme · turn a failure into a success.

## Governance Requirements

Already enforced and extending to this package without change: I-19 (construction), I-12 (connections), I-2 (`service_role`).

New, AST-based where practical:

- **I-26** — no `jwt.decode`, `jwt.get_unverified_*`, or equivalent outside `app/auth/`.
- **I-27** — no logging call whose arguments reference the `Authorization` header or a token.
- **I-25** — a handler that calls `request_transaction` must take a `VerifiedIdentity` parameter.

Each with a violating fixture that fails and a compliant fixture that passes.

## Operational Implications

- FastAPI and an ASGI server become runtime dependencies. Both are ratified by `ADR-0058`.
- The verifier and JWKS cache are built once per process and shared; the identity is per request.
- A JWKS outage returns 401 for every request until the cache refills — the fail-closed posture from `ADR-0063` section 3, surfacing at the HTTP layer as blanket 401s rather than a distinct status, consistent with I-24.
- The single route introduced is a boundary probe. It is not a product endpoint and is expected to be replaced by real routes.

## Rollback / Reversal Strategy

- Weakening any part of I-24 — a more helpful error, a distinguishing status — is a forward-fix, never a revert. Partial relaxations are silent oracles.
- Reverting to header parsing inside handlers requires a superseding ADR and is expected to be rejected.
- The code-level rollback target is `v0.4.0-auth-boundary`.

## Consequences

- An HTTP request cannot reach a protected operation without passing the cryptographic boundary, and cannot obtain an identity by any other route.
- Handlers become simpler: they receive an identity and cannot be tempted by claims they never see.
- Cost: every protected route must declare the dependency. That verbosity is the control.
- Rate limiting remains outstanding and is explicitly inherited, not discharged.
- One generic 401 makes client-side debugging harder. Correlation ids exist so a server-side log can answer what the response deliberately will not.

## Verification Approach

- Governance asserts I-25, I-26 and I-27 statically; the test suite asserts the rest.
- Mutation testing proves each property is defended by a specific test rather than incidentally.
- The integration test proves the whole chain: HTTP → dependency → identity → `SET LOCAL` → RLS → caller-owned rows only.
- No claim is made that the HTTP layer is "secure" generally. It defends the enumerated threats; H5 and H9 carry stated residual risk.
