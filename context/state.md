# Project Heartbeat & Task State

> **Last Heartbeat:** 2026-08-10
> **Project State:** STAGE 0 IN PROGRESS — slice 1 complete, slice 2 not started
> **Current baseline:** `v0.3.0-rls-harness`
> **Profile:** `aaroh` (see `profiles/aaroh.yaml`)

---

## Where the project stands

Six foundational decisions are ratified and merged into `main`, the Aaroh-specific AgentOS governance that enforces them is live in CI, and **Stage 0 slice 1 is complete**: the database security boundary is now executable rather than documented.

Application code exists, but only the security boundary: one table, the sanctioned database access layer, and its test suites. No product feature, no client, no AI.

| Checkpoint | Contents |
|-----------|----------|
| `v0.1.0-agentos-ready` | ADR-0057…0060, `profiles/aaroh.yaml`, Aaroh standards, `llm-reviewer`, QG-009…011, CI enforcement, protected `main` |
| `v0.2.0-security-boundary` | ADR-0061 v1.1 (RLS and the data access boundary), ADR-0062 (raw SQL migrations), and the CI checks enforcing them |
| **`v0.3.0-rls-harness`** | **Stage 0 slice 1 — sanctioned `backend/app/db/` access layer, first raw SQL migration, CI auth shim, 29 RLS tests, 10 governance regression tests** |

---

## Current Sprint Tasks

- `[x]` Reconstruct and validate the environment on macOS
- `[x]` Architecture review of the product specification against vendored AgentOS
- `[x]` Ratify ADR-0057 (licence), ADR-0058 (stack), ADR-0059 (engine), ADR-0060 (weights)
- `[x]` Create `profiles/aaroh.yaml` and Aaroh-specific standards, reviewer, and gates
- `[x]` Ratify ADR-0061 (RLS and the data access boundary) and ADR-0062 (migration strategy)
- `[x]` **Stage 0 slice 1 — RLS test harness** (PR #7, merged `fa4738e`, tagged `v0.3.0-rls-harness`)
- `[ ]` **Next approved work — Stage 0 slice 2: Supabase Auth + JWT verification** (design report first)

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

## Next approved work — Stage 0 slice 2

**Supabase Auth + JWT verification.** Completes the identity path:

```
Client -> Supabase Auth -> JWT -> verification (signature, exp, iss, aud)
      -> verified identity -> request_transaction() -> SET LOCAL -> RLS
```

Slice 1 built the second half; slice 2 builds the first. **No login or signup UI** — the cryptographic boundary is proven before any interface is drawn.

A design report precedes implementation, and implementation requires separate approval.

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
