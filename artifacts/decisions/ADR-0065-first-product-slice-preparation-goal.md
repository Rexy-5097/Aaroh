---
id: ART-ADR-0065
title: "First Product Slice: The Preparation Goal"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-10
modified: 2026-08-10
related_adr: ADR-0059
related_standard: standards/privacy.md
related_checklist: QG-011
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0065

> **Status:** Accepted | **Date:** 2026-08-10 | **Decider:** Rexy-5097

## Context

Slices 1–3 built and proved a complete security chain: RLS, JWT verification, and the HTTP boundary. None of it is a product capability. Aaroh now has to start proving it solves the problem it exists for.

The product answers one question: **what is the highest-value use of my next 90 minutes?** `ADR-0059` fixes the shape of the machinery that answers it:

```
rank(snapshot, constraints, catalog) -> RankedResult
```

Three inputs. `snapshot` is the student's current readiness state, `catalog` the candidate tasks, and `constraints` what bounds the answer. The product's governing rule — *no recommendation without deadline and time-budget context* — says the engine may not run at all without the third.

**Nothing in the repository supplies any of them.** The schema is one `profiles` table with a display name.

## Problem Statement

What is the smallest end-to-end capability that is genuinely part of Aaroh — not scaffolding — and that every later capability depends on?

## Alternatives Considered

**Option A — DSA tracker first.** Rejected as first. It supplies part of `snapshot`, which is real. But `context/state.md` records an unresolved blocker: **LeetCode has no official public API**, so ingestion is manual-entry-or-nothing pending ADR-0072. Starting here means starting on the one input whose acquisition is undecided.

**Option B — Resume analyzer first.** Rejected, and it is the strongest "no" of the set. It requires untrusted file handling, private storage with signed URLs, a PII minimisation pipeline, and an AI provider — **four decisions `context/state.md` lists as open**, at least two of which are Stage-0 blocking. It is also the largest attack surface in the product. Building it first means building the most dangerous thing before its safety decisions exist.

**Option C — Career Readiness Score first.** Rejected. The score is a *function of* DSA state, resume state and constraints. With no inputs it would be a constant, and shipping a number that means nothing is the exact "opaque score" the product defines itself against.

**Option D — Decision engine skeleton first.** Rejected. `rank()` needs all three inputs. A skeleton with no data is infrastructure without a product requirement — the thing the brief for this slice explicitly warns against — and `ADR-0060` would require golden files pinning weights nobody has evidence for yet.

**Option E — The preparation goal: target role, deadline, weekly hours.** **Accepted.**

## Decision

The first product capability is the **preparation goal**: a student states what they are preparing for, by when, and how many hours a week they have.

### Why this one

1. **It is the `constraints` argument of `ADR-0059`'s contract**, directly. Not a step toward it — the thing itself.
2. **The product rule makes it a precondition.** No recommendation may exist without a deadline and a time budget, so no later capability can ship before this does.
3. **It is the only input with no open decisions in front of it.** DSA needs ADR-0072, resume needs four. This needs none.
4. **It is genuinely small**: one table, two endpoints, no file handling, no external service, no AI.
5. **Ownership is trivially clean under RLS** — one row per student, `user_id` as the primary key, exactly the shape slice 1 proved.
6. **It is user-facing capability without needing a UI.** A student can state a goal and read it back; a client can be built against it later.

### What is stored

`public.preparation_goals`, one row per student:

| Column | Rule |
|--------|------|
| `user_id` | Primary key, `DEFAULT auth.uid()`, cascades from `auth.users` |
| `target_role` | Required, 1–120 characters |
| `target_company` | Optional, ≤120 characters |
| `deadline` | Required date, must be in the future, within 730 days |
| `weekly_hours` | Required, 1–80 |

`user_id` defaults to `auth.uid()` so application code never supplies an owner and therefore cannot supply the wrong one. The `WITH CHECK` policy is the control; the default is belt and braces.

**`target_role` is free text, not an enumeration.** A fixed list of roles would be wrong within a semester, and the engine treats the value as an opaque key until role-specific weighting is designed and evidenced.

### Where validation lives, and why it is split

- **Database**: shape — lengths and ranges, as `CHECK` constraints.
- **Domain layer**: judgement — the deadline must be in the future and within a sane horizon; hours must be plausible rather than merely physical.

The split is not stylistic. A `CHECK` against `now()` is not `IMMUTABLE`, so PostgreSQL will not accept it — and it would be wrong anyway: a row valid when written must not become invalid merely because time passed. Temporal validity is an input rule, not a storage rule.

The domain layer takes **`today` as an argument** and never reads a clock, mirroring `ADR-0059`'s discipline. Every temporal rule is then testable without freezing time.

Two judgement bounds worth naming: **80 hours a week**, not the physical 168, because a student claiming more is describing an intention rather than a plan and the engine would rank against time that does not exist; and a **730-day horizon**, beyond which a date is a career aspiration rather than a preparation deadline.

### What the Decision Engine gets, and what it does not

This slice **implements no ranking**. It supplies the `constraints` input and stops.

`days_remaining` is derived on read, never stored — a stored value would be wrong the next morning. It is presentation; the engine receives the raw `deadline` and computes what it needs from an explicit `now` (`ADR-0059`).

No `decision_engine` package is created. Doing so would trigger the purity gate and `ADR-0060`'s golden-file requirement for weights that have no evidence behind them.

### API

Path-versioned under `/v1`. Two endpoints, both requiring the slice-3 dependency:

- `PUT /v1/preparation-goal` — create or replace. **PUT, not POST**: a student has exactly one active goal, so this is idempotent replacement, not collection append.
- `GET /v1/preparation-goal` — read own goal, `404` when absent.

**The 404 is doing real work.** Under RLS another student's goal is not visible, so "not set" and "belongs to someone else" are indistinguishable — the anti-enumeration behaviour `ADR-0061` section 6 requires, obtained with no special-case code.

Validation failures return **422 naming the offending field**. Unlike an authentication failure — deliberately uniform under `ADR-0064` I-24 — this discloses nothing about any other user, so being specific is a kindness rather than an oracle.

**OpenAPI as a published contract is not ratified here.** FastAPI generates a schema; committing to it as *the* contract, with client generation, remains an open decision in `context/state.md`.

### Security invariant

| ID | Invariant |
|----|-----------|
| **I-30** | A request model never declares an owner identifier. The owner comes from the verified identity (`ADR-0061` I-4), never from the request body. |

A request model with a `user_id` field is IDOR-by-design: the endpoint invites the client to name whose data it is operating on, and only a predicate stands between that and a breach. Enforced by an AST governance check.

## What is deliberately NOT built

No DSA schema · no resume schema or storage · no readiness score · no ranking · no AI or provider abstraction · no notifications, analytics, events or payments · no organisation, tenant, or recruiter tables · **no `tenant_id` anywhere** · no mobile or web UI · no generic profile table of unused fields · no CRUD for its own sake.

`profiles` is untouched. This slice adds exactly one table because exactly one is needed.

## Threat Model

| # | Threat | Mitigation | Residual |
|---|--------|-----------|----------|
| P1 | A student reads another's goal | RLS `USING (user_id = auth.uid())`; proven both directions through HTTP | Low |
| P2 | A student writes a goal owned by another | `WITH CHECK`, plus `DEFAULT auth.uid()`. Proven by a direct-SQL test that names another owner explicitly — the API alone could not prove it | Low |
| P3 | The request body chooses the owner | `extra="forbid"`, no owner field, I-30 check | Low |
| P4 | Unauthenticated access | Slice-3 dependency on both endpoints; asserted to persist nothing | Low |
| P5 | Invalid constraints reach the engine later | Domain validation, mirrored by database `CHECK`s | Low |
| P6 | Goal data is personal | `target_role` and `target_company` reveal job-seeking intent — **High-class** under `standards/privacy.md`. Protected by the same RLS boundary; never logged, never sent anywhere | Moderate — deletion and export remain unbuilt (`ADR-0061` section 9) |

## Testing Strategy

Minimum coverage, not a target. A test asserting only HTTP 200 proves nothing.

**Domain (pure):** accepted goals · trimming · optional company · boundary cases on every bound · past and same-day deadlines · horizon limit · non-integer hours including `True`, since `bool` is an `int` subclass and would otherwise pass silently · required text · `days_remaining` changing with `today`.

**API and isolation:** set and read back · replacement not duplication · 404 when absent · **A cannot read B's goal and B cannot read A's** · writes do not overwrite another's row · a client-supplied `user_id` is ignored · unauthenticated requests refused and persisting nothing · a rejected role refused · invalid input rejected with the field named and persisting nothing.

**Direct-SQL:** an `INSERT` naming another owner and an `UPDATE` reassigning ownership are both refused — the tests that make `WITH CHECK` load-bearing, since the API never supplies `user_id` and so cannot exercise it.

**Structural:** the slice-1 catalogue assertions cover the new table with no edit — that was their purpose.

**Mutation testing is mandatory**, as in slices 1–3.

## Operational Implications

- One forward-only migration (`ADR-0062`). No data migration; the table is new.
- Adds no runtime dependency: FastAPI and Pydantic arrived with slice 3.
- The `/internal/boundary-probe` route from slice 3 remains and should be deleted once real routes carry the same proof.

## Rollback / Reversal Strategy

- Forward-fix only for the migration (`ADR-0062`). Dropping the table would destroy student-entered goals.
- Rollback target is `v0.5.0-http-boundary`.
- Reversing the *choice* of first slice costs one table and two endpoints — deliberately cheap, because it is a product bet rather than a security decision.

## Consequences

- Aaroh has its first real capability, and the `constraints` input the engine cannot run without.
- The schema grows by exactly one table, with the ownership shape every later table will copy.
- Cost: no visible product yet — there is no UI, and a student cannot see a recommendation because none is computed.
- The next slice can be chosen on product grounds rather than blocked on security ones.

## Verification Approach

- Cross-user isolation asserted in both directions through HTTP, not merely for one user.
- `WITH CHECK` proven by direct SQL, since the API cannot exercise it.
- Mutation testing proves each property is defended by a specific test.
- No claim is made that the capability is complete: it stores constraints and returns them. It does not yet influence any recommendation, because none exists.
