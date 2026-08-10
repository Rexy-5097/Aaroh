---
id: ART-ADR-0061
title: "Row-Level Security and the Data Access Boundary"
version: 1.1
status: accepted
owner: Rexy-5097
created: 2026-08-10
modified: 2026-08-10
related_adr: ADR-0062
related_standard: standards/privacy.md
related_checklist: QG-011
related_workflow: master.md
related_agent: security-reviewer
---

# Architecture Decision Record: ADR-0061

> **Status:** Accepted | **Date:** 2026-08-10 | **Decider:** Rexy-5097
>
> **v1.1** — adds the sanctioned database access path (I-12) and development/production project separation (I-11), and ratifies migration tooling via `ADR-0062`. Amended before merge in response to review of v1.0.

## Context

Aaroh stores resumes, contact details, employment history, target employers, DSA activity, and a continuous behavioural record of a student's preparation. `standards/privacy.md` classifies most of this **High**. A cross-user data leak would expose a user's job search to their current employer, and is the single worst technical outcome available to this product.

`ADR-0058` ratified Supabase PostgreSQL, Auth, and Storage behind a FastAPI modular monolith. That leaves the most consequential question unanswered: **under whose identity does a database query actually execute?**

Supabase provides Row-Level Security, and it is the highest-leverage control available. But it has a specific, widely-tripped failure mode: **the `service_role` key carries `BYPASSRLS`.** A backend that connects with `service_role` — the default in most FastAPI + Supabase tutorials — silently disables every RLS policy in the database. The policies still exist, still appear in migrations, still look like a security posture in a review, and enforce nothing. Isolation then rests entirely on every developer remembering `WHERE user_id = ...` on every query forever.

That is the decision this ADR makes, along with the boundary rules for the seven other components that touch user data.

**Scope.** This ADR defines the access model, the invariants, and the test strategy. It does **not** define the application schema, and adds no migrations. Table design is a later decision that must conform to this one.

## Problem Statement

How do Expo/React Native clients, web clients, FastAPI, Supabase Auth, PostgreSQL, Storage, background workers, and the future AI gateway obtain access to user data such that user isolation is enforced *structurally* — surviving a forgotten `WHERE` clause, a new developer, and a route written in a hurry — rather than by convention?

## Alternatives Considered

**Option A — Backend connects as `service_role`; ownership enforced in application code.**
Rejected. This is the common pattern and it is the reason these products leak. RLS becomes decorative: policies exist but never execute. Every one of the hundreds of queries Aaroh will eventually contain becomes an independent opportunity for an IDOR, and the failure is silent — a missing predicate returns *more* data, and tests written against a single user's fixtures pass. It optimises for the first week of development and pays for it permanently.

**Option B — Clients talk directly to Supabase (PostgREST); no backend in the data path.**
Rejected. Genuinely secure for CRUD, since RLS is the only path. But `ADR-0059` places the canonical decision engine in the Python backend, and Aaroh needs server-side orchestration for scoring, resume extraction, and decision traces. It would also push business logic into clients, which `ADR-0059` forbids. Retained as a *supplementary* path for Storage only, where Supabase's own signed-URL mechanism is the appropriate tool.

**Option C — Backend propagates the authenticated user's identity into every request-scoped transaction; connects as a role without `BYPASSRLS`; RLS enforces isolation.**
**Accepted.** A forgotten `WHERE` clause returns the caller's own rows rather than everyone's. The database, not the developer, is the enforcement point.

**Option D — Per-user database roles or schema-per-user.**
Rejected. True isolation, but role/schema sprawl at even a few hundred users, painful migrations, and no support in Supabase Auth's model. Solves a multi-tenant problem Aaroh does not have.

**Option E — Option C, but with `service_role` retained "just for admin work".**
Rejected as stated, and refined into the accepted decision. An unscoped escape hatch becomes the default path under deadline pressure. `service_role` survives only for the two purposes that genuinely cannot be expressed under RLS (below), and never inside a request handler.

## Decision

### 1. Identity flows into the database on every request

FastAPI connects to PostgreSQL using an application role that **does not** hold `BYPASSRLS`. Every request-scoped database access runs inside an explicit transaction that first establishes the caller's identity:

```
BEGIN;
  SET LOCAL ROLE authenticated;
  SET LOCAL request.jwt.claims = '<validated claims JSON>';
  -- queries here; auth.uid() resolves to the caller
COMMIT;
```

`SET LOCAL` is transaction-scoped. It cannot survive into the next request on a pooled connection — **provided every request runs inside a transaction**. That proviso is invariant **I-3** and is tested, because plain `SET`, or a query issued outside a transaction, would leak one user's identity to the next request on the same connection. That is the most dangerous bug this design can produce, and it is why the transaction boundary is an invariant rather than a convention.

The claims JSON is built **only from claims FastAPI has already cryptographically verified**. Raw client-supplied tokens are never interpolated into the GUC.

### 2. Which operations may use `service_role`

| Actor | Credential | RLS applies |
|-------|-----------|-------------|
| Request handlers (all CRUD) | app role → `SET LOCAL ROLE authenticated` | **Yes** |
| Per-user background jobs | app role, impersonating the job's subject | **Yes** |
| Cross-user aggregate jobs | dedicated `aaroh_worker` role, narrow grants | **Yes** |
| Migrations (DDL) | migration credential, CI/deploy only | N/A |
| Break-glass admin | `service_role`, audited, human-initiated | No |

**`service_role` is permitted for exactly two purposes: schema migrations, and human-initiated break-glass operations.** Its key is never present in the runtime environment of any request-serving process, and never in any client. A request handler that reaches for it is a defect, not a shortcut (**I-2**).

### 3. Background workers do not get a master key

A worker processing user X's resume runs under **user X's identity**, using the same `SET LOCAL` mechanism with claims constructed by the worker from its own trusted job record — not from user input. The job row names its subject; the worker adopts that subject and nothing more.

This matters more than it first appears. The resume parser is Aaroh's largest attack surface (`standards/privacy.md`, and the untrusted-file decision still pending). If a malicious PDF achieves code execution inside a worker holding `service_role`, the attacker owns every user's data. If the worker holds only the current user's context, the attacker gains what they already had: their own resume.

Genuinely cross-user work — nightly aggregates, cohort statistics — uses a dedicated `aaroh_worker` role with explicit, minimal table grants and its own RLS policies. It is a restricted role, not a bypass. Aggregate jobs read only what they need and write only to aggregate tables.

### 4. RLS policy requirements

Every user-owned table:

- has a single canonical ownership column, `user_id`, referencing the auth user;
- has `ENABLE ROW LEVEL SECURITY` **and** `FORCE ROW LEVEL SECURITY`, the latter because a table's owner otherwise bypasses its own policies — a silent and common gap;
- defines both `USING` (rows visible) **and** `WITH CHECK` (rows writable) predicates. `USING` alone permits a user to *insert or update a row owned by someone else*, which is the second-most-common RLS mistake after forgetting `FORCE`;
- denies `anon` entirely;
- is created with its RLS enabled and its policies defined **in the same migration that creates the table** (**I-5**). A table that exists for even one deploy without policies is a table that was fully exposed.

Default posture is deny: RLS enabled with no matching policy returns zero rows rather than erroring. Aaroh fails closed and loudly at the application layer rather than open at the data layer.

### 5. Authentication and authorization are separate

**Authentication** (who is calling) is Supabase Auth. FastAPI independently verifies each JWT — signature, `exp`, `iss`, `aud` — against the project's signing key. An unverified token never reaches the database context. Forwarding a token without verifying it would make RLS trust whatever the client asserted, converting the strongest control into the weakest.

**Authorization** is two distinct layers:

- **Data-level (RLS):** which *rows*. Structural, in the database.
- **Operation-level (service layer):** which *actions* — quotas, rate limits, entitlement, state-machine legality (e.g. "may this mission be completed twice?"). RLS cannot express these and must not be asked to.

RLS answers "which rows", never "which operations". Conflating them produces either unenforceable policies or business logic in SQL.

### 6. IDOR prevention

The primary control is structural: under RLS, another user's row is not visible, so a handler that looks up an object by a client-supplied identifier finds nothing. Supporting rules:

- The acting user id is derived **only** from the verified JWT, never from a path, query, body, or header (**I-4**).
- Identifiers are opaque UUIDs. This is defence in depth, not a control.
- A request for an object the caller cannot see returns **404, not 403** — a 403 confirms the object exists, turning the error code into an enumeration oracle.

### 7. Storage and signed URLs

Resumes live in a **private** bucket, path-namespaced by owner:

```
resumes/{user_id}/{resume_id}.{ext}
```

A `storage.objects` policy restricts access to objects whose first path segment equals the caller's id, so the client's own Supabase session cannot read another user's object.

Signed URLs are generated **server-side only**, and **the ownership check happens before the URL is signed** (**I-6**). This is not a stylistic preference: a signed URL is a bearer capability that deliberately bypasses RLS. The pre-signing authorization check is therefore the *only* control on that path, and its absence is unrecoverable.

- Download TTL: **≤ 5 minutes**. Upload TTL: **≤ 15 minutes**.
- The object path is derived server-side from the authenticated identity and the resume record — **never** from a client-supplied path, which would be path traversal into another user's namespace.
- Signed URLs are never logged, never placed in query strings of onward requests, and never returned in analytics payloads.

### 8. The AI gateway is not a database client

The AI gateway holds **no database credential**. It receives an already-constructed, already-minimised payload from a domain service and returns validated structured output. It cannot query, cannot widen its own access, and cannot be induced by prompt injection to fetch data it was not given — because there is no code path from the gateway to the database.

This complements `ADR-0059`: the decision engine cannot import the gateway, and the gateway cannot reach the database. Neither boundary depends on the other, and neither depends on developer discipline.

### 9. Deletion propagates as a tracked, resumable operation

Deletion spans systems that fail independently, so it is **not** a single transaction. A `deletion_request` record drives a resumable state machine:

| Target | Action |
|--------|--------|
| PostgreSQL user-owned rows | Deleted (FK cascade from the user record) |
| Derived data — scores, traces, recommendations, missions | Deleted by the same cascade |
| **Supabase Storage objects** | **Explicitly deleted.** Storage objects are *not* removed by database cascade — the most commonly missed step, leaving resumes behind after "deletion" |
| Pending background jobs | Cancelled and tombstoned before row deletion, so no job resurrects data |
| Analytics (PostHog) | Pseudonymous id deletion requested via the provider's API |
| Audit records | **Retained**, with the subject pseudonymised — the conflict `standards/privacy.md` requires be resolved explicitly |

The request is only complete when every step reports success. Partial deletion is a tracked, retryable state, never a silent one.

### 10. Audit logging

Access to High-class data is recorded from the first release. Audit rows are written through a `SECURITY DEFINER` function so the application role can append but cannot modify or delete. The audit table grants no `UPDATE` or `DELETE` to any application role.

Records carry actor, action, resource type and id, timestamp, and request id — **never the data itself**. An audit log containing resume contents is a second copy of the data with weaker controls.

Users may read their own audit trail. That is a transparency feature consistent with Aaroh's product principles, not merely a compliance artifact.

### 11. Migrations

Migrations are versioned, reviewed as security changes, and forward-only in any deployed environment. A migration that creates a user-owned table without enabling and forcing RLS and defining policies is rejected by CI (**I-5**).

Migration tooling is ratified separately by **`ADR-0062`**, which mandates raw SQL for all RLS-sensitive DDL precisely so the I-5 check remains reliable. The requirements above are tool-independent; ADR-0062 makes them mechanically enforceable.

### 12. The sanctioned database access path

There is exactly one place in Aaroh where a database connection may be created: the **`db/` package inside the backend** (for example `backend/app/db/`). It owns the engine, the connection pool, and the request-scoped session dependency that opens the transaction and applies `SET LOCAL`.

Every other module — routes, services, domain logic, workers — obtains a session from that dependency and never constructs its own. A module that imports a driver or calls a connection factory directly has, by construction, bypassed the transaction wrapper and therefore invariant I-3, because identity is established by the dependency and nowhere else.

This is invariant **I-12**, and unlike a convention it is checked statically (`check_db_access_boundary`). Two exemptions, both narrow: migration tooling, and the test suite — the RLS tests must open raw connections as different roles in order to prove isolation, which is the entire point of them.

### 13. Development and production are separate Supabase projects

Aaroh runs **at least two entirely separate Supabase projects**: `aaroh-dev` and `aaroh-prod`. They are distinct projects with distinct URLs, distinct JWT signing keys, distinct `service_role` keys, and distinct storage buckets. This is not a naming convention inside one project — a single project with a "dev" schema shares one `service_role` key, so any development-time leak is a production breach.

| Rule | Requirement |
|------|-------------|
| Separation | Development and production are separate Supabase projects. No credential is valid in both. |
| Production credentials | Never present on a developer workstation, never in `.env` files, never in the repository. They exist only in the deployment platform's secret store. |
| Development credentials | May exist locally in a gitignored `.env`. Still never committed — `.gitignore` blocks `.env*`, and CI's secret scan is the backstop. |
| `service_role` keys | Both projects' keys live only in CI/deploy secret stores. The development key is not a lesser secret; it is a full bypass for whatever data the development project holds. |
| Production data in development | Prohibited. Development uses synthetic or self-authored data. Copying production resumes into a development project would place real personal data in the weaker environment — the exact inversion of this control. |
| Rotation | On any suspected exposure, on maintainer change, and on a scheduled basis at least every 90 days. Rotation is a documented procedure, not an improvised response. |
| Key inventory | Every credential that exists is recorded — which project, where stored, last rotated. A key nobody remembers issuing cannot be rotated. |

A third `aaroh-staging` project is warranted before public launch, when a change needs verification against production-like data volumes without touching production. It is not warranted at Stage 0 and is deliberately deferred.

This is invariant **I-11**. Its absence is what turns a routine development mistake into a reportable breach, and it costs nothing to establish now versus untangling shared credentials later.

## Security Invariants

Violation of any of these is a CRITICAL finding. None may be waived to unblock a release.

| ID | Invariant |
|----|-----------|
| **I-1** | The application database role never holds `BYPASSRLS`. |
| **I-2** | No request-serving process has the `service_role` key in its environment. |
| **I-3** | Every request-scoped database access occurs inside a transaction that sets identity with `SET LOCAL`. Never plain `SET`; never outside a transaction. |
| **I-4** | The acting user identity derives only from a cryptographically verified JWT — never from client-supplied path, query, body, or header. |
| **I-5** | Every user-owned table has RLS enabled **and forced**, with both `USING` and `WITH CHECK` policies, from the migration that creates it. |
| **I-6** | Ownership is verified before a signed URL is generated, and object paths are derived server-side. |
| **I-7** | Background workers act under a specific subject's identity or a narrowly granted worker role — never with RLS bypassed. |
| **I-8** | The AI gateway holds no database credential. |
| **I-9** | Audit records are append-only and contain no High-class data values. |
| **I-10** | Disabling RLS is never an acceptable remedy to an incident or a failing test. |
| **I-11** | Development and production are separate Supabase projects. No credential is valid in both, production credentials never exist on a developer workstation, and production data is never copied into development. |
| **I-12** | Database connections and clients are created only inside the sanctioned `db/` access layer. Exemptions: migration tooling and the test suite. |

## Data-Flow Boundary

```
 Expo / RN client          Web client
        │                      │
        │  Supabase Auth JWT   │
        └──────────┬───────────┘
                   ▼
        ┌────────────────────────┐
        │  FastAPI               │
        │  1. verify JWT         │  ← authentication
        │  2. operation policy   │  ← authorization (actions)
        │  3. BEGIN; SET LOCAL   │
        └───┬──────────────┬─────┘
            │              │
            │              └──────────────┐
            ▼                             ▼
 ┌──────────────────────┐      ┌────────────────────┐
 │ PostgreSQL           │      │ AI Gateway         │
 │ role: authenticated  │      │ NO DB CREDENTIAL   │
 │ RLS ENFORCED         │      │ minimised payload  │
 └──────────────────────┘      └─────────┬──────────┘
            ▲                            ▼
            │                    ┌────────────────┐
            │                    │ LLM provider   │
 ┌──────────┴───────────┐        └────────────────┘
 │ Workers              │
 │ per-user identity OR │        ┌────────────────────────────┐
 │ aaroh_worker role    │        │ Supabase Storage (private) │
 │ never service_role   │        │ resumes/{user_id}/...      │
 └──────────────────────┘        │ signed URL ≤ 5 min,        │
                                 │ ownership checked BEFORE   │
 ┌──────────────────────┐        │ signing                    │
 │ Migrations (CI only) │        └────────────────────────────┘
 │ service_role / owner │
 │ never in app runtime │
 └──────────────────────┘
```

## Threat Model

| # | Threat | Mitigation | Residual risk |
|---|--------|-----------|---------------|
| T1 | Authenticated user reads another user's resume via IDOR | RLS (I-1, I-5), identity from JWT only (I-4), storage policy, pre-sign check (I-6), 404 not 403 | Low |
| T2 | **`service_role` key leaks** | Never in client or app runtime (I-2); CI secrets only; rotation | **Accepted and material.** A leak exposes all data. This is the design's largest single point of failure |
| T3 | Forged or expired JWT | Independent signature/`exp`/`iss`/`aud` verification before the GUC is set (I-4) | Low |
| T4 | Identity leaks between requests on a pooled connection | `SET LOCAL` + mandatory transaction (I-3), tested explicitly | Low, but catastrophic if regressed — hence a dedicated test |
| T5 | Signed URL leaks via sharing, logs, or referrer | ≤ 5 min TTL, never logged | Low; bounded by TTL |
| T6 | Malicious resume achieves code execution in a worker | Worker holds only the subject's identity (I-7); no bypass credential to steal | Moderate — worker sandboxing is a separate pending decision |
| T7 | Prompt injection makes the AI layer fetch other users' data | Gateway has no database credential (I-8) | Very low |
| T8 | Migration adds a table without RLS | CI check (I-5) fails the PR | Low |
| T9 | Client sends another user's id in a request body | Identity never read from the request (I-4); RLS rejects regardless | Very low |
| T10 | Developer adds a query outside the transaction wrapper | Session dependency is the only sanctioned access path; I-3 test | Moderate — depends on the dependency being the only route |
| T11 | Backup or PITR snapshot exposure | Managed by Supabase; provider-dependent | Accepted; provider trust is inherent to ADR-0058 |
| T12 | Insider or maintainer access | Audit logging (I-9), least privilege | Accepted at solo-maintainer scale; stated honestly |
| T13 | Development-environment leak reaches production data | Separate projects, no shared credential, no production data in development (I-11) | Low. Bounds T2: a development key leak now costs synthetic data, not real resumes |
| T14 | A module opens its own connection, bypassing the identity wrapper | Sanctioned `db/` layer is the only connection site (I-12), checked statically | Low — this closes the gap that made I-3 depend on discipline |

## Failure Modes

| Failure | Cause | Detection | Recovery |
|---------|-------|-----------|---------|
| Total data exposure, silent | Backend connects as `service_role` | I-1/I-2 CI checks; role assertion test | Rotate key, redeploy with app role, audit access logs |
| Cross-user write allowed | Policy has `USING` but no `WITH CHECK` | Per-table policy matrix test | Add `WITH CHECK`; audit for writes |
| Owner bypasses own policies | `FORCE ROW LEVEL SECURITY` omitted | Catalogue assertion test | Add FORCE; re-verify |
| One user sees another's data intermittently | Plain `SET`, or query outside a transaction | Dedicated context-leak test (I-3) | Fix session dependency; treat as an incident |
| App breaks, no data returned | RLS enabled, no matching policy | Integration tests | Add the policy — **never** disable RLS (I-10) |
| Resumes survive account deletion | Storage objects not cascaded | Deletion integration test | Reconcile orphaned objects; fix the state machine |
| Pooler errors under load | Transaction-mode pooling with prepared statements | Load testing before Stage 2 | Disable statement caching or use session mode |

## Testing Strategy

RLS is testable without Supabase: the semantics are PostgreSQL's. CI runs a Postgres service container with a minimal `auth` schema shim providing `auth.uid()` and the `authenticated`/`anon` roles, applies migrations, and asserts behaviour.

**Honest limitation:** the shim must match Supabase's real `auth.uid()` definition. If it drifts, tests pass while production differs — a false assurance worse than no test. The shim is pinned to Supabase's documented definition, carries a comment saying so, and is re-verified against a real Supabase development project at each stage boundary.

### Tier B — application tests (pytest)

**Structural, automatically covering future tables** — these are the tests that matter most, because they need no update when a table is added:

1. Every table in the application schema has `relrowsecurity` **and** `relforcerowsecurity` true.
2. Every such table has at least one policy, with both `USING` and `WITH CHECK` present for write commands.
3. The application role does not hold `BYPASSRLS`.
4. `anon` holds no grants on application tables.

**Per-table isolation matrix**, for users A and B:

5. A selects own rows → returns them.
6. A selects B's rows → **zero rows**, not an error.
7. A updates/deletes B's rows → zero rows affected.
8. A inserts a row with `user_id = B` → rejected by `WITH CHECK`.

**Boundary tests:**

9. Identity does not leak: two sequential transactions on the *same pooled connection* under different subjects each see only their own rows.
10. A request that never opens a transaction cannot read user data.
11. A tampered, expired, or wrong-issuer JWT is rejected before any database access.
12. A request supplying another user's id in the body still acts as the caller.
13. Storage: A cannot read `resumes/{B}/...`; a signed URL is refused before generation when the caller is not the owner; TTL is within bounds.
14. Deletion: after completion, no rows, **no storage objects**, no pending jobs remain; audit rows remain with the subject pseudonymised.
15. Audit rows cannot be updated or deleted by the application role.

### Tier A — AgentOS governance (CI, no database)

16. `VS-027`: a migration creating a user-owned table without RLS enabled, forced, and policied fails governance.
17. A source scan finds no `service_role` reference in request-handling code (I-2).
18. No module outside the sanctioned `db/` layer imports a driver or calls a connection factory (I-12). Migrations and tests are exempt.
19. Migration files are raw SQL; a Python migration that generates DDL fails, because it would defeat check 16 (`ADR-0062`).
20. The AI gateway imports no database client (I-8).

The Tier A/Tier B split is the one established in the architecture review: AgentOS governance validates that the rules exist; the application suite validates that the code obeys them.

## Operational Implications

- **Two credentials, separately scoped, per environment.** An application role (no `BYPASSRLS`) in runtime; a migration credential in CI/deploy secrets only. They never appear in the same environment — and `aaroh-dev` and `aaroh-prod` never share any of them (I-11).
- **Every request opens a transaction.** A fixed cost paid once in a session dependency, but it means no long-running request may hold a connection while awaiting an external call — relevant to LLM-calling routes, which must complete their database work before invoking the gateway.
- **Connection mode.** Session mode (port 5432) for the MVP: simpler, and it avoids transaction-pooler interactions with prepared statements. Transaction pooling is revisited when connection count actually justifies it, not before.
- **Local development** uses a managed Supabase development project (`ADR-0058`), so RLS and JWT behaviour under test match production. A local Postgres container would not.
- **Break-glass is a procedure, not a habit.** Human-initiated, recorded, and followed by rotation.
- **Cost:** near zero at MVP scale. RLS predicate evaluation on indexed `user_id` columns is negligible for 10–200 users.

## Rollback / Reversal Strategy

**Rolling back a security migration can open access.** A down-migration that drops a policy or disables RLS is not a neutral operation, and standard rollback intuitions are actively dangerous here.

- Security migrations are **forward-fix only** in any deployed environment. A defective policy is replaced by a new, tightened migration — never reverted to the prior looser state.
- `ALTER TABLE ... DISABLE ROW LEVEL SECURITY` is never an acceptable remedy for an incident or a failing test (**I-10**).
- Reversing this ADR's *architecture* — moving to `service_role` plus application-layer checks — would require a superseding ADR and a full audit of every query, and is expected to be rejected. The reversal path exists for completeness, not as a plan.
- The code-level rollback target for the change that introduces this model is the preceding release tag, per `docs/ENGINEERING_WORKFLOW.md`. Reverting application code does not revert applied migrations; any PR carrying a migration states its undo path explicitly.

## Consequences

- Isolation becomes a property of the database rather than of developer vigilance. A forgotten predicate degrades to "user sees their own data", not "user sees everyone's".
- Compromise of a worker, a request handler, or the AI layer yields one user's data at most, not the corpus.
- Cost: a mandatory transaction wrapper, two credentials to manage, and a genuine learning curve around `SET LOCAL`, `FORCE`, and `WITH CHECK` — each of which has a specific, well-known failure mode now covered by a test.
- The schema decision that follows is constrained: every user-owned table needs a `user_id` column and policies in its creating migration.
- `service_role` key leakage remains the largest single point of failure and is accepted, not solved.

## Verification Approach

- CI asserts I-1, I-2, I-5 statically; the Tier B suite asserts the remainder against a real PostgreSQL instance.
- The structural tests (schema-wide RLS assertions) cover tables that do not yet exist, so the guarantee extends automatically as Aaroh grows.
- QG-011 gates any change adding a user-owned table, an external data flow, or a storage path.
- No claim is made that this design satisfies any compliance regime. It is an engineering control set. DPDP obligations, including the unresolved under-18 question in `standards/privacy.md`, are a separate decision.
