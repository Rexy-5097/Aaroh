# Project Heartbeat & Task State

> **Last Heartbeat:** 2026-08-10
> **Project State:** INITIALIZED — Stage 0 not started
> **Profile:** `aaroh` (see `profiles/aaroh.yaml`)

---

## Where the project stands

Environment reconstructed on macOS from the GitHub source of truth and validated. Architecture review completed. The first four foundational decisions are ratified (ADR-0057 – ADR-0060) and Aaroh-specific AgentOS governance is in place.

**No application code exists.** That is intentional and correct for this stage.

---

## Current Sprint Tasks

- `[x]` Run validation suite and confirm PASS status
- `[x]` Architecture review of product spec against vendored AgentOS
- `[x]` Ratify ADR-0057 (licence), ADR-0058 (stack), ADR-0059 (engine), ADR-0060 (weights)
- `[x]` Create `profiles/aaroh.yaml` and Aaroh-specific standards, reviewer, and gates
- `[ ]` Decide the remaining Stage-0-blocking architecture decisions (below)
- `[ ]` Begin Stage 0 — **blocked pending those decisions**

---

## Open decisions blocking Stage 0

| Topic | Why it blocks |
|-------|--------------|
| Supabase RLS enforcement model | `service_role` bypasses RLS entirely; the security posture depends on this |
| AI provider selection | Needs current data-retention terms verified at decision time |
| PII minimisation pipeline | Gates every external model call |
| Resume ingestion / untrusted file handling | Largest attack surface; precedes any upload code |
| OpenAPI as contract + client type generation | Prevents drift across shells |

## Known unresolved risks

- **DPDP / under-18 users.** Target users include 17-year-olds. Public-launch blocker, not a Stage 0 blocker. See `standards/privacy.md`.
- **Cold start.** A new user with no resume and no DSA history must still get a useful first session.
- **LeetCode has no official public API.** Manual entry for V1; Codeforces has an official API (verify terms before committing).

---

## Baseline to protect

Bootstrap self-test PASS · synthetic suite 21/21 · validator 83/100 with 0 broken references. The 83/100 is **not** a target to raise — three validator categories audit AgentOS's own v1.0.0 release, not Aaroh. See `DEVELOPMENT_SETUP.md` §5.
