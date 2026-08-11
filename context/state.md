# Project Heartbeat & Task State

> **Last Heartbeat:** 2026-08-11
> **Project State:** STAGE 0 — security foundation complete; two product data sources and the engine's snapshot input built. Engine not started.
> **Current baseline:** `v0.9.0-snapshot-builder`
> **Profile:** `aaroh` (see `profiles/aaroh.yaml`)

---

## Where the project stands

Eleven Aaroh decisions (ADR-0057…0067) are ratified and merged, the governance enforcing them runs in CI, and the security chain is executable rather than documented: RLS, JWT verification and the HTTP boundary.

Two of the decision engine's four inputs now have real sources, and its `snapshot` input is built. **The engine itself does not exist** — `rank()` is unwritten, and the engine purity check is still ARMED because there is nothing yet to police. No catalogue, no weights, no AI, no client.

| Checkpoint | Contents |
|-----------|----------|
| `v0.1.0-agentos-ready` | ADR-0057…0060, `profiles/aaroh.yaml`, Aaroh standards, `llm-reviewer`, QG-009…011, CI enforcement, protected `main` |
| `v0.2.0-security-boundary` | ADR-0061 v1.1 (RLS and the data access boundary), ADR-0062 (raw SQL migrations), and the CI checks enforcing them |
| `v0.3.0-rls-harness` | Stage 0 slice 1 — sanctioned `backend/app/db/` access layer, first raw SQL migration, CI auth shim, 29 RLS tests, 10 governance regression tests |
| `v0.4.0-auth-boundary` | Slice 2 — asymmetric JWT verification via JWKS, `VerifiedIdentity`, claim minimisation (ADR-0063) |
| `v0.5.0-http-boundary` | Slice 3 — dependency-injected identity, uniform 401, no second trust path (ADR-0064) |
| `v0.6.0-preparation-goal` | Product slice 1 — the engine's `constraints` input (ADR-0065) |
| `v0.7.0-dsa-activity` | Product slice 2 — append-only DSA practice log, manual entry only (ADR-0066) |
| `v0.8.0-snapshot-contract` | Decision-only — the readiness snapshot contract (ADR-0067) |
| **`v0.9.0-snapshot-builder`** | **Product slice 3 — `StudentSnapshot` built from DSA history by bounded SQL aggregation; domain purity check added** |

---

## Current Sprint Tasks

- `[x]` Reconstruct and validate the environment on macOS
- `[x]` Architecture review of the product specification against vendored AgentOS
- `[x]` Ratify ADR-0057 (licence), ADR-0058 (stack), ADR-0059 (engine), ADR-0060 (weights)
- `[x]` Create `profiles/aaroh.yaml` and Aaroh-specific standards, reviewer, and gates
- `[x]` Ratify ADR-0061 (RLS and the data access boundary) and ADR-0062 (migration strategy)
- `[x]` **Stage 0 slice 1 — RLS test harness** (PR #7, `v0.3.0-rls-harness`)
- `[x]` **Stage 0 slice 2 — Supabase Auth + JWT verification** (PR #10, `v0.4.0-auth-boundary`)
- `[x]` **Stage 0 slice 3 — HTTP authentication boundary** (PR #11, `v0.5.0-http-boundary`)
- `[x]` **Product slice 1 — preparation goal** (PR #12, `v0.6.0-preparation-goal`)
- `[x]` **Product slice 2 — DSA activity record** (PR #13, `v0.7.0-dsa-activity`)
- `[x]` **Snapshot contract, decision only** (PR #14, `v0.8.0-snapshot-contract`)
- `[x]` **Product slice 3 — snapshot builder** (PR #15, `v0.9.0-snapshot-builder`)
- `[ ]` **BLOCKED — the decision engine contract.** Six decisions are missing before `rank()` can be
  written; see "Decisions required before the engine" below. Implementation must not start first.

---

## Stage 0 slice 1 — complete

**PR #7 merged** as `fa4738e263ef441ac3eb40e04c2792c0fc247c04`, tagged `v0.3.0-rls-harness`.

Proven: **Aaroh can establish user identity at the database boundary, and PostgreSQL itself prevents cross-user access.**

| | |
|---|---|
| RLS tests | **29/29** passing on PostgreSQL 16.4 in CI; deterministic and re-runnable |
| Governance regression tests | **10/10** — I-5 whitespace hardening pinned in both directions |
| Mutation testing | Complete. Removing `FORCE`, removing `WITH CHECK`, `SET LOCAL` → `SET`, and granting `BYPASSRLS` each make the suite fail |
| Identity-leak test | Repaired so it fails *on its own* under the `SET LOCAL` → `SET` mutation; connection reuse asserted via `pg_backend_pid()`, not assumed |
| `NON_USER_OWNED_TABLES` | **Removed.** Not required by the current architecture; a blank security exemption is worse than a future addition failing loudly |
| Governance checks | Six moved ARMED → active: I-2, I-5, I-8, I-12, engine purity, excluded infrastructure |

Shipped: `backend/app/db/session.py` (the only module permitted to open a connection), `supabase/migrations/20260810120000_create_profiles.sql` (RLS enabled **and forced**, `USING` + `WITH CHECK`, `anon` revoked), `backend/tests/sql/auth_shim.sql` (CI-only, pinned to Supabase's documented `auth.uid()`).

### Limitations carried forward

- **The `auth.uid()` CI shim is the weakest link.** Pinned and commented; if Supabase changes the definition and the shim is not updated, tests pass while production differs. Re-verify at each stage boundary.
- CI runs PostgreSQL **16.4**; keep this aligned with the Supabase project's version.
- Sync `psycopg`, not async — deliberate for readability; mechanical to swap when a web framework arrives.
- The mutation-proof test duplicates the wrapper's logic in a leaky variant; it asserts its own preconditions and fails "inconclusive" rather than silently passing, but it is a second copy of a pattern.

---

## Decisions required before the engine

`rank()` cannot be written until these exist. Each was searched for and is genuinely
absent, not merely undocumented — recorded here so the gap is visible rather than
rediscovered.

| # | Missing decision | Why it blocks |
|---|-----------------|---------------|
| ~~E1~~ | ~~Version identifier mechanism~~ | **Partly settled by ADR-0068**: an immutable human-readable label identifies an artifact, with a SHA-256 digest of its exact bytes as an integrity check; labels are never reused. The label *format* is deliberately still open, as are lifecycle, coexistence and per-user pinning. |
| E2 | **Output contract** | `RankedResult` is a name with no fields. Investigated and **blocked**: it cannot be defined without task identity (E3), score semantics, tie-breaking and confidence semantics. Note ADR-0059's field list sits under a heading titled *Clients* and describes the **API response**, not `rank()`'s return value — the two are currently conflated. |
| ~~E3~~ | ~~Catalogue contract~~ | **Settled by ADR-0069** (DSA-only V1): slug identity, `TOPICS` tags, difficulty reused with distinct meaning, no time estimate, versioned file rather than a table. Originally blocked at: nothing in the repository defines what a recommended *task* is. `context/architecture.md` says "career-preparation tasks", `README.md` says "single action" — phrases, not definitions. No task taxonomy, no identity scheme, no example item, no fields. Whether the catalogue is DSA-only or spans domains (resume, mock interviews) is undecided, and that single answer determines identity, fields, topic optionality and difficulty semantics. ADR-0067 §8 fixes only the join: catalogue topic tags must come from the same `TOPICS` tuple. |
| E4 | **Weights semantics** | ADR-0060 fixes the architectural contract and states explicitly that no weight values are defined by it. Their shape, units and provenance format remain open. |
| E5 | **Cold-start behaviour** | The requirement is recorded below; the behaviour is not. Default task selection, fallback ranking, minimum evidence and catalogue filtering are all undecided. |
| E6 | **Tie-breaking and trace completeness** | No rule exists for equal scores — and byte-identical output (ADR-0059) makes a deterministic tie-break mandatory, not optional. ADR-0060's trace omits a catalogue version and a retention period, the latter required by `standards/privacy.md` for every data class. |

| E4 | **Score model** | Investigated and **blocked**. *"Readiness gain"* appears exactly twice in the repository (`context/architecture.md`, `ADR-0060`) and is described, never defined. ADR-0060 §Context states outright that *"every coefficient in that calculation is, today, a hypothesis with no supporting evidence"*. Nothing defines how solving one DSA problem changes readiness, and no score scale, range, direction, type or precision exists anywhere. |

**S1 is already settled by existing decisions — no new ADR was needed.** The quantity
that orders candidate tasks is **not** the Career Readiness Score:

- `ADR-0065` defines the Career Readiness Score as *"a function of DSA state, resume
  state and constraints"* — three inputs, and **no candidate parameter**. A quantity
  that takes no candidate cannot order candidates.
- `context/vision.md` ships them a stage apart: Stage 1 delivers *"transparent score +
  confidence. **No recommender yet**"*, Stage 2 delivers *"ROI ranking"*. A quantity
  that exists for a whole stage without any ranking is not the ranking quantity.
- Nothing anywhere equates the two. `ADR-0060` shows the Career Readiness Score is also
  weight-driven and engine-computed — shared machinery, not shared identity.

**Consequence: V1 ranking does not require resume state.** `ADR-0067` §9 guarantees a
snapshot is total and valid with zero history, so the engine has a usable input today.
This is a derivation from accepted decisions, not a new decision, and it should be
recorded as a premise in the score-model ADR rather than in an ADR of its own.

Two structural findings from the score-model investigation:

- **The Career Readiness Score cannot be computed in V1.** `ADR-0065` defines it as *"a function of DSA state, resume state and constraints"* — and resume state is deferred, with V1 approved as DSA-only. One of its three inputs does not exist.
- **The ranking score and the Career Readiness Score are separable, and separating them unblocks V1.** `ADR-0059`'s contract is `rank()`, not `score_readiness()`; `README.md` says *"Aaroh is not a score… the score exists to make that decision inspectable"*; `context/vision.md` says *"the decision engine is the product"*. The engine needs a per-candidate **ordering** quantity, which needs no resume data. Conflating the two is what makes the score model look blocked on data it does not require.

Two findings from the E2 and E3 investigations that are not blockers but change scope:

- **The decision trace is High-class, and nothing currently says so.** ADR-0060 stores `constraints | deadline, time budget, target role`, and `standards/privacy.md` classes *target role* and *target company* as **High**. ADR-0067 deliberately kept the snapshot uniformly Medium so traces would not be promoted; the constraints half re-introduces High regardless. This pulls in audit logging and minimisation before any external call, and must be settled with the trace.
- **A task catalogue would be Aaroh's first non-user-owned table.** `backend/tests/test_rls_structural.py` anticipates this explicitly and will fail loudly until an exemption is designed — *"an explicit allow-list keyed to an ADR, with the exempted table still asserted for the properties that do apply"*. The catalogue is therefore a security decision as well as a product one. |

**`rank()` arity is also stated two ways** — three arguments in ADR-0059 §"Conceptual
contract" and ADR-0065 (which quotes it), four in ADR-0060 §Consequences and
`standards/decision_engine.md`. The evidence favours four, but resolving it is an
owner decision and no ADR text has been amended.

---

## Open decisions still blocking later Stage 0 work

| Topic | Why it blocks |
|-------|--------------|
| Core domain model / schema | Must conform to ADR-0061: `user_id` column, policies in the creating migration |
| Resume ingestion / untrusted file handling | Largest attack surface; precedes any upload code |
| AI provider selection | Needs current data-retention terms verified at decision time |
| PII minimisation pipeline | Gates every external model call |
| OpenAPI as contract + client type generation | Prevents drift across shells |

## Known unresolved risks

- **DPDP / under-18 users.** Target users include 17-year-olds. Public-launch blocker, not a Stage 0 blocker. See `standards/privacy.md`.
- **`service_role` key leakage** remains a single point of total compromise. ADR-0061 I-11 bounds it; it does not eliminate it.
- **The `auth.uid()` CI shim** must match Supabase's real definition, or tests pass while production differs.
- **I-11 and I-14 are policy, not automation.** No CI check can verify separate Supabase projects or the absence of dashboard schema edits.
- **Cold start.** A new user with no resume and no DSA history must still get a useful first session.
- **LeetCode has no official public API.** Manual entry for V1; Codeforces has an official API (verify terms before committing).

---

## Baseline to protect

Bootstrap self-test PASS · synthetic suite 21/21 · validator 83/100 with 0 broken references. The 83/100 is **not** a target to raise — three validator categories audit AgentOS's own v1.0.0 release, not Aaroh. See `DEVELOPMENT_SETUP.md` §5 and ADR-0057.

Seven governance checks are **ARMED**: they report as such while their subject does not exist, and begin failing on violation the moment Stage 0 code appears.
