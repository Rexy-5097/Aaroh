---
id: ART-ADR-0063
title: "JWT Verification and the Authentication Boundary"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-10
modified: 2026-08-10
related_adr: ADR-0061
related_standard: standards/security.md
related_checklist: QG-005
related_workflow: master.md
related_agent: security-reviewer
---

# Architecture Decision Record: ADR-0063

> **Status:** Accepted | **Date:** 2026-08-10 | **Decider:** Rexy-5097

## Context

`ADR-0061` built the second half of Aaroh's identity path: a verified identity is carried into PostgreSQL by `SET LOCAL`, and row-level security decides which rows it may reach. Stage 0 slice 1 implemented and mutation-tested that half.

The first half does not exist. `ADR-0061` **I-4** states that the acting identity "derives only from a cryptographically verified JWT" — but nothing in the codebase performs that verification, and `request_transaction(pool, claims: dict)` accepts any dictionary a caller hands it. The strongest control in the system currently depends on a convention.

Two specific failure modes make this urgent rather than theoretical:

1. **Forwarding an unverified token** would make RLS trust whatever the client asserted. `auth.uid()` would return an attacker-chosen subject, and every policy would faithfully enforce access *for the wrong user*.
2. **Algorithm confusion.** If a verifier accepts both asymmetric and HMAC algorithms, an attacker can sign a token with HMAC using the *public* key as the shared secret. A permissive verifier accepts it. The live project makes this concrete: `/.well-known/openid-configuration` advertises `id_token_signing_alg_values_supported: ["RS256","HS256","ES256"]` while the JWKS contains ES256 only. The server's capability list is not the project's configuration, and neither is the token's own `alg` header.

**Scope.** This ADR decides how a Supabase-issued JWT becomes a trusted identity, and what reaches PostgreSQL. It does not define API routes, session management, refresh handling, sign-in flows, or any user interface.

## Verified provider facts

Every value below was observed against the live `aaroh-dev` project (ref `wpgrwkupxokzoeopmqjj`), not taken from documentation. Where a documented behaviour could not be observed, it is marked as such and the design still handles it.

| Fact | Observed value | Status |
|------|---------------|--------|
| Signing algorithm | `ES256` (EC, P-256, `use: sig`, `key_ops: ["verify"]`) | **VERIFIED** |
| Asymmetric active | Yes — JWKS exposes public material only, no private parameter | **VERIFIED** |
| Issuer | `https://wpgrwkupxokzoeopmqjj.supabase.co/auth/v1` | **VERIFIED** (OpenID configuration) |
| JWKS URL | `<issuer>/.well-known/jwks.json` | **VERIFIED** |
| JWKS authentication | **None required** — HTTP 200 with no header | **VERIFIED** |
| JWKS cache header | `cache-control: public, max-age=600` | **VERIFIED** |
| Signing keys present | 1 (`kid` is a UUID string) | **VERIFIED** |
| `aud` | `"authenticated"` — a **string**, not an array | **VERIFIED** |
| `role` | `"authenticated"` | **VERIFIED** |
| `sub` | UUID | **VERIFIED** |
| `is_anonymous` | `false` | **VERIFIED** |
| `aal` / `session_id` | `"aal1"` / present | **VERIFIED** |
| Access-token lifetime | **3600 s** (`exp - iat`) | **VERIFIED** |
| Anonymous sign-ins | Disabled | **VERIFIED** |
| Full claim set | `aal, amr, app_metadata, aud, email, exp, iat, is_anonymous, iss, phone, role, session_id, sub, user_metadata` | **VERIFIED** |
| `aud` as an array | Documented, **not observed** on this project | **NOT VERIFIED** — handled anyway |
| Key rotation states | Documented (standby → in use → previously used → revoked); only one key exists | **NOT VERIFIED** — handled anyway |

Note the claim set: a Supabase access token carries `email`, `phone`, `user_metadata`, and `app_metadata`. That directly motivates the claim-minimisation decision below.

## Problem Statement

How does a Supabase-issued JWT become a trusted identity at Aaroh's boundary, such that an unverified or attacker-crafted token cannot reach PostgreSQL, and such that no more personal data than RLS requires enters database session state?

## Alternatives Considered

**Option A — Trust the token, decode without verification.** Rejected outright. This is the failure ADR-0061 I-4 exists to prevent: RLS would enforce policies for an attacker-chosen `sub`.

**Option B — Symmetric verification with the legacy shared JWT secret (HS256).** Rejected. The secret both verifies *and signs*, and it is the same secret behind the `service_role` key. Anyone obtaining it can mint a `service_role` token and bypass RLS entirely. Aaroh would also have to store a signing-capable secret in every request-serving process, directly worsening the blast radius that ADR-0061 I-2 works to contain. Supabase itself recommends against it.

**Option C — Asymmetric verification against the project's JWKS.** **Accepted.** Aaroh holds only public verification material. A total compromise of Aaroh's configuration still cannot forge a user.

**Option D — Delegate verification to Supabase's `/auth/v1/user` endpoint on every request.** Rejected. Correct, but adds a network round trip to every authenticated request, makes Aaroh's availability depend on Supabase Auth's, and provides no benefit over local verification with a cached public key.

**Option E — Verify locally but skip JWKS caching, fetching keys per request.** Rejected. Same latency and availability problems as D, plus it makes Aaroh a trivial amplification vector against the provider.

## Decision

### 1. Asymmetric verification with a pinned algorithm allow-list

Verification accepts **`ES256` and `RS256` only**. `HS256` and `none` are rejected, as is any algorithm outside the list.

The allow-list is passed to the verification library explicitly and is **never derived from the token's `alg` header**. This is the algorithm-confusion defence: with a pinned asymmetric-only list, a token signed by HMAC using the public key as the secret fails, because the library never selects an HMAC verification path.

`RS256` is included despite the project currently using `ES256`, so that a provider-side migration between asymmetric algorithms does not require an Aaroh code change. Adding `HS256` to this list is a security regression and is blocked by governance.

### 2. Claim validation

Every check below is mandatory. Failure of any one rejects the token.

| Claim | Rule |
|-------|------|
| signature | Must verify against a JWKS key selected by `kid` |
| `exp` | Required. Expired tokens rejected, with 30 s leeway |
| `nbf` | If present, must not be in the future, same 30 s leeway |
| `iat` | Required |
| `iss` | Required. **Exact string equality** with the configured issuer — never prefix, suffix, or substring matching, which would accept `https://evil.example/https://<ref>.supabase.co/auth/v1` |
| `aud` | Required. Must equal `"authenticated"`, **or** be a list containing it. Both forms are handled; only the string form was observed live |
| `sub` | Required, non-empty, and a **valid UUID**. It becomes `auth.uid()`, which is typed `uuid` in PostgreSQL — a non-UUID subject would fail at the database boundary rather than the authentication boundary, which is the wrong place to find out |
| `role` | Must equal `"authenticated"`. `anon` and `service_role` are rejected |
| `is_anonymous` | If present and `true`, rejected |

**Clock skew: 30 seconds.** Small enough that it does not meaningfully extend a token's life (0.8% of the observed 3600 s lifetime), large enough to absorb ordinary drift between Supabase's clock and Aaroh's host. A larger allowance would be a silent extension of every token's validity.

**Rejecting `service_role` is not redundant.** ADR-0061 I-2 keeps the key out of request-serving processes, but that does not stop a client *presenting* a `service_role` token it obtained elsewhere. Such a token is validly signed by the same project. Its `role` claim is the distinguishing signal, and the verifier is where it must be caught. Note also that `service_role` and `anon` tokens carry `iss: "supabase"` rather than the project issuer, so exact issuer matching rejects them independently — two controls, deliberately.

**Rejecting anonymous users** reflects the current architecture: anonymous sign-ins are disabled on the project, and no Aaroh feature is designed for an identity that owns no durable data. If an anonymous flow is ever wanted, that is a product decision requiring its own ADR, not a verifier relaxation.

### 3. JWKS retrieval, caching, and rotation

| Behaviour | Decision |
|-----------|----------|
| Cache lifetime | **600 s**, matching the provider's own `cache-control: max-age=600`. Choosing a longer TTL would hold keys past the point the provider expects them refreshed |
| Normal request | Uses the cached key set. No network call |
| Unknown `kid` | Triggers **at most one** refresh, then retries verification once |
| Refresh rate limit | **At most one unknown-`kid` refresh per 60 s.** Without this, an attacker sending random `kid` values turns every request into an outbound fetch — a free amplification vector against the provider and a self-inflicted denial of service |
| Rate-limited miss | The token is **rejected**. It is never accepted on the grounds that the key set might be stale |
| Fetch failure | **Fail closed.** Tokens are rejected while JWKS is unreachable |
| Fallback | **None.** Never accept an unverified token, never skip signature verification, never fall back to a shared secret |

**Rotation** is handled by this design without special cases. Supabase rotates by publishing a new key while keeping the previous one valid; tokens signed by the old key remain verifiable until they expire. A token bearing a new `kid` is a cache miss, triggers one refresh, and verifies against the newly published key.

**Availability trade-off, stated plainly.** Fail-closed means a JWKS outage lasting longer than the cache TTL makes Aaroh reject all requests. That is the correct trade for a product holding resumes: failing open would accept unverified tokens, which is unbounded compromise rather than bounded downtime.

### 4. `VerifiedIdentity` — an honest boundary

`request_transaction` stops accepting `dict` and accepts a `VerifiedIdentity` carrying only:

- `subject` — the validated UUID from `sub`
- `role` — always `"authenticated"` at present

**What this does and does not guarantee.** Python has no true private constructor. A frozen dataclass alone would look like a boundary while enforcing nothing, because any module could write `VerifiedIdentity(subject=..., role=...)`. The defence is therefore layered, and its limits are stated rather than glossed:

| Layer | Stops | Does not stop |
|-------|-------|---------------|
| Private construction sentinel — `__init__` requires a module-private token held only by the verifier | Accidental construction; construction by a developer who has not read this ADR | A determined caller reaching the sentinel via `sys.modules`, or `object.__new__` |
| AST governance check — construction outside the auth package fails CI | Deliberate bypasses reaching `main` | Nothing, if the check is deleted — hence CODEOWNERS on `.github/scripts/` |
| Tests | Regression | — |
| Code review | Intent | — |

The honest claim is: **direct construction fails loudly at runtime, and a bypass cannot reach `main` without deleting a governed CI check.** Not: the type is unforgeable. Overclaiming a boundary is worse than a documented one, because it stops people looking.

### 5. Claim minimisation — a correction to slice 1

Slice 1 serialises the **entire** claims dictionary into `request.jwt.claims`. Against a real Supabase token that means `email`, `phone`, `user_metadata`, and `app_metadata` enter PostgreSQL session state — where they can surface in `pg_stat_activity`, query logs, and error output.

`standards/privacy.md` classifies email and phone as **High**, and `ADR-0061` I-9 forbids High-class values in audit records for the same reason. This ADR corrects it: **only `sub` and `role` reach the database.**

`auth.uid()` reads `sub`; the RLS policies written in slice 1 need nothing else. Any future policy needing another claim requires a deliberate decision to widen this set, reviewed under QG-011.

### 6. Dependency and boundary rules

**`PyJWT[crypto]`** is the verification library — maintained, widely reviewed, supports ES256/RS256 and JWKS via `PyJWKClient`, and compatible with the Python 3.12 used in CI. Aaroh does not implement JWT parsing or signature verification itself.

**A runtime manifest is created.** `backend/requirements-dev.txt` states in its own header that it is *not* an application manifest, and `ADR-0058` left Python packaging deliberately unlocked. `PyJWT` is a runtime dependency, so quietly adding it to a dev-only file would misrepresent what Aaroh ships. `backend/requirements.txt` is introduced for runtime dependencies; the dev manifest includes it by reference.

**Direction of dependency.** `auth` produces `VerifiedIdentity`; `db` consumes it. The auth package imports no database driver and opens no connection — `ADR-0061` I-12 already forbids connections outside `db/`, and governance enforces it. The database layer knows nothing of JWKS, signatures, or rotation.

### 7. Error semantics

All verification failures produce **one** generic authentication failure to the caller. The specific reason — bad signature, expired, wrong issuer, wrong role — is recorded server-side with a request identifier and never returned. Distinguishing them to the client turns the endpoint into a token-validation oracle and can leak account existence.

**Never logged:** raw tokens, `Authorization` headers, signatures, or any High-class claim. Logs may record the failure category, the `kid`, and the request id.

## Security Invariants

Extends the ADR-0061 set:

| ID | Invariant |
|----|-----------|
| **I-15** | JWT signature verification is never disabled. No production code path decodes a token without verifying it. |
| **I-16** | The verification algorithm allow-list contains only asymmetric algorithms. `HS256` and `none` never appear. |
| **I-17** | `iss` is compared by exact string equality; `aud` must contain `authenticated`; `sub` must be a UUID; `role` must be `authenticated`. |
| **I-18** | JWKS failure, or a rate-limited unknown `kid`, rejects the token. Verification never fails open. |
| **I-19** | `VerifiedIdentity` is constructed only inside the authentication package. |
| **I-20** | Only `sub` and `role` are propagated into `request.jwt.claims`. No other claim reaches PostgreSQL. |
| **I-21** | The authentication package holds no database credential and opens no connection. |

## Data-Flow Boundary

```
 Client (Expo / web)
        │  Authorization: Bearer <supabase access token>
        ▼
 ┌──────────────────────────────────────────────┐
 │ auth/  (no database credential, I-21)        │
 │  1. extract bearer token                     │
 │  2. JWKS cache -> key by kid                 │
 │       miss -> ONE refresh, rate limited 60s  │
 │       unavailable -> REJECT (I-18)           │
 │  3. verify signature, algorithms pinned      │
 │       ES256 | RS256 only          (I-16)     │
 │  4. validate exp/nbf/iss/aud/sub/role (I-17) │
 │  5. construct VerifiedIdentity    (I-19)     │
 └───────────────────┬──────────────────────────┘
                     │  VerifiedIdentity(subject, role)  -- nothing else
                     ▼
 ┌──────────────────────────────────────────────┐
 │ db/  (sanctioned access layer, ADR-0061)     │
 │   BEGIN                                      │
 │   set request.jwt.claims = {sub, role} (I-20)│
 │   SET LOCAL ROLE authenticated               │
 └───────────────────┬──────────────────────────┘
                     ▼
            PostgreSQL — RLS, auth.uid() = sub
                     ▼
              user-owned rows only
```

## Threat Model

| # | Threat | Mitigation | Residual |
|---|--------|-----------|----------|
| J1 | Forged token, attacker-chosen `sub` | Signature verified against provider JWKS (I-15) | Low |
| J2 | **Algorithm confusion** — HMAC-signed token using the public key as secret | Pinned asymmetric-only allow-list (I-16); `alg` header never trusted | Low |
| J3 | `alg: none` | Same allow-list | Low |
| J4 | Expired token replayed | `exp` enforced, 30 s leeway | Low — bounded by the 3600 s lifetime |
| J5 | Token from a different Supabase project | Exact `iss` equality (I-17) | Low |
| J6 | `service_role` token presented by a client | `role` rejected, and `iss` differs (two independent controls) | Low |
| J7 | `anon` or anonymous-user token | `role` and `is_anonymous` checks; anonymous sign-ins disabled provider-side | Low |
| J8 | Unknown-`kid` flood forcing outbound fetches | One refresh per 60 s; rate-limited misses rejected | Low |
| J9 | JWKS poisoning via MITM | HTTPS with certificate validation to the provider host | Accepted — inherent to trusting the provider (ADR-0058) |
| J10 | JWKS outage | Fail closed (I-18) | **Accepted: bounded downtime, chosen over unbounded compromise** |
| J11 | PII leaking into database session state, logs, `pg_stat_activity` | Only `sub` and `role` propagate (I-20) | Low |
| J12 | Token or header written to logs | Prohibited by §7; governance and review | Moderate — a convention until a log-scrubbing check exists |
| J13 | `VerifiedIdentity` forged by application code | Sentinel + AST governance (I-19) | **Moderate and explicitly stated** — see §4 |
| J14 | Verification bypassed by disabling signature checking | I-15, AST governance check | Low |
| J15 | Stolen valid token | Out of scope for this ADR — bounded by the 3600 s lifetime; revocation and refresh handling are a later decision | **Accepted** |

## Failure Modes

| Failure | Cause | Detection | Recovery |
|---------|-------|-----------|---------|
| Every token accepted | Signature verification disabled | I-15 governance check; mutation test | Restore verification; treat as an incident; rotate provider keys |
| Cross-project tokens accepted | Substring or prefix `iss` matching | Wrong-issuer test | Exact equality |
| Privilege escalation | `role` unchecked | `service_role` / `anon` rejection tests | Add the check; audit access |
| Amplification against provider | Unknown-`kid` refresh unbounded | Rate-limit test | Restore the limiter |
| Total auth outage | JWKS unreachable beyond cache TTL | Fail-closed test; monitoring | Restore connectivity — **never** relax to fail-open |
| PII in `pg_stat_activity` | Full claims propagated | Minimisation test asserting the payload | Restore minimisation; consider log rotation |
| Type boundary hollow | `VerifiedIdentity` constructed elsewhere | Direct-construction test; AST check | Restore; review how it was reached |

## Testing Strategy

Tests use **locally generated ES256 and RS256 keypairs** and a local JWKS fixture. No production key material, and no live provider dependency — the suite must be deterministic and offline.

**Verification unit tests:** valid ES256 · valid RS256 · invalid signature · expired · future `nbf` · wrong issuer · wrong audience · audience as array · missing `sub` · non-UUID `sub` · malformed token · `alg: none` · HS256 rejected · **algorithm confusion** (HMAC signed with the public key) · unknown `kid` · key rotation · JWKS unavailable → fail closed · rate-limited refresh → rejected · `service_role` rejected · `anon` rejected · anonymous user rejected.

**Boundary tests:** direct `VerifiedIdentity` construction fails · a plain dict is refused by `request_transaction` · only `sub` and `role` appear in `request.jwt.claims` · no `email`/`phone`/metadata reaches PostgreSQL.

**Integration:** a locally minted valid token → `VerifiedIdentity` → `request_transaction` → `auth.uid()` → RLS returns only that user's rows, and a second identity cannot see the first's. This must run against real PostgreSQL, reusing slice 1's harness.

**Mutation testing is mandatory**, following slice 1's discipline. Each mutation must be caught by a *named* test, and the specific test recorded: disabled signature verification · removed `exp` · removed `iss` · removed `aud` · `HS256` added to the allow-list · `alg: none` permitted · `service_role` accepted · `anon` accepted · UUID validation removed · unknown-`kid` refresh removed · full claims propagated to the database. A mutation that survives means the property is unprotected regardless of how many tests pass.

## Governance Requirements

AST-based where practical; string matching only where semantics do not permit better:

- **I-15** — no `verify_signature: False`, and no unverified decode, in production code.
- **I-16** — no algorithm list containing `HS256` or `none`.
- **I-19** — `VerifiedIdentity` constructed only inside the auth package.
- **I-21** — the auth package imports no database driver.

Each check is tested in both directions, with a violating fixture that must fail and a compliant fixture that must pass. Exemptions are not created speculatively.

## Operational Implications

- Configuration is **non-secret**: project ref (or issuer URL) and JWKS URL. No key, secret, or token is required for verification, so nothing sensitive enters the runtime environment for this purpose.
- Steady-state verification is local and fast: no network call on the cached path.
- `aaroh-dev` and production are separate projects with different issuers and key sets (ADR-0061 I-11), so the issuer must be configuration, never a hardcoded constant.
- Token lifetime is 3600 s, so a revoked user retains access for at most an hour. Shortening it is a provider setting, and session revocation is a later decision.

## Rollback / Reversal Strategy

- **Forward-fix only** for verification defects. A "temporary" relaxation of any claim check is a silent authentication bypass; there is no safe partial state.
- Reverting to unverified decoding, or to HS256, requires a superseding ADR and is expected to be rejected.
- The code-level rollback target is the preceding release tag per `docs/ENGINEERING_WORKFLOW.md`. Rolling back the claim-minimisation change would reintroduce PII into database session state and must not be done casually.

## Consequences

- Identity becomes cryptographically established rather than asserted, completing the chain ADR-0061 began.
- Aaroh holds **no signing-capable secret** for authentication. Full configuration compromise still cannot forge a user.
- PII stops entering PostgreSQL session state — a slice 1 defect corrected before any feature depends on it.
- Cost: a runtime dependency, a JWKS cache to reason about, and a fail-closed availability coupling to the provider's JWKS endpoint.
- `VerifiedIdentity` adds a type to every call site that reaches the database. That verbosity is the point.

## Verification Approach

- Governance checks assert I-15, I-16, I-19, and I-21 statically; the test suite asserts the rest.
- Mutation testing proves each security property is defended by a specific test rather than incidentally.
- The end-to-end test proves the whole chain: token → verification → `VerifiedIdentity` → `SET LOCAL` → RLS → user-owned rows only.
- No claim is made that this design is "secure" in general. It defends the enumerated threats; J9, J10, J12, J13, and J15 carry stated residual risk.
