# Project Heartbeat & Task State

> **Last Heartbeat:** 2026-08-10
> **Project State:** INITIALIZED — **Stage 0 implementation has NOT started**
> **Current baseline:** `v0.2.0-security-boundary`
> **Profile:** `aaroh` (see `profiles/aaroh.yaml`)

---

## Where the project stands

Environment reconstructed on macOS from the GitHub source of truth and validated. Architecture review completed. Six foundational decisions are ratified and merged into `main`, and the Aaroh-specific AgentOS governance that enforces them is live in CI.

**No application code exists.** No backend, no clients, no schema, no migrations, no AI implementation. That is intentional and correct for this stage.

| Checkpoint | Contents |
|-----------|----------|
| `v0.1.0-agentos-ready` | ADR-0057…0060, `profiles/aaroh.yaml`, Aaroh standards, `llm-reviewer`, QG-009…011, CI enforcement, protected `main` |
| **`v0.2.0-security-boundary`** | **ADR-0061 v1.1 (RLS and the data access boundary), ADR-0062 (raw SQL migrations), and the CI checks enforcing them** |

---

## Current Sprint Tasks

- `[x]` Reconstruct and validate the environment on macOS
- `[x]` Architecture review of the product specification against vendored AgentOS
- `[x]` Ratify ADR-0057 (licence), ADR-0058 (stack), ADR-0059 (engine), ADR-0060 (weights)
- `[x]` Create `profiles/aaroh.yaml` and Aaroh-specific standards, reviewer, and gates
- `[x]` Ratify ADR-0061 (RLS and the data access boundary) and ADR-0062 (migration strategy)
- `[~]` **Stage 0 vertical slice 1 — RLS test harness: implemented, awaiting review**

---

## Stage 0 vertical slice 1 — in review

Implemented on `stage0/vertical-slice-01-rls`. **Not merged.**

The first Aaroh application code: the CI auth shim, a pinned PostgreSQL service, the sanctioned access layer at `backend/app/db/`, the first raw SQL migration (`public.profiles`), and the Tier B isolation and structural test suites.

What it proves: **Aaroh can establish user identity at the database boundary, and PostgreSQL itself prevents cross-user access.** Verified by mutation — removing `FORCE`, removing `WITH CHECK`, changing `SET LOCAL` to `SET`, and granting `BYPASSRLS` each make the suite fail.

Six governance checks moved from ARMED to active: I-2, I-5, I-8, I-12, engine purity, and excluded infrastructure.

Still absent by design: Supabase Auth, JWT verification, API routes, clients, AI, decision engine, and any schema beyond one table.

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
