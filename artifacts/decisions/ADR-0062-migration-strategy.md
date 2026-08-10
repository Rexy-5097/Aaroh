---
id: ART-ADR-0062
title: "Database Migration Strategy"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-10
modified: 2026-08-10
related_adr: ADR-0061
related_standard: standards/privacy.md
related_checklist: QG-011
related_workflow: master.md
related_agent: security-reviewer
---

# Architecture Decision Record: ADR-0062

> **Status:** Accepted | **Date:** 2026-08-10 | **Decider:** Rexy-5097

## Context

`ADR-0061` makes row-level isolation structural, and invariant **I-5** requires that every user-owned table have RLS enabled, forced, and policied *in the migration that creates it*. The governance check enforcing I-5 reads migration files and asserts those statements are present.

That check has a blind spot, identified in review of ADR-0061 v1.0 before any code was written: **it only works if migrations are readable as SQL.** Under a Python-based migration tool such as Alembic, a table is created by `op.create_table(...)` — a Python call that emits DDL at runtime. The check would scan the file, find no `CREATE TABLE`, and report compliance. A table would ship with no RLS and CI would go green.

A security check that silently stops working is worse than no check, because it is trusted. This ADR removes the blind spot by deciding the migration technology rather than leaving it tool-independent.

There is a second, independent reason to decide it here. RLS policies are the security boundary. A reviewer approving a policy change must read **the exact SQL that will run against the database** — not a Python DSL that generates it. `USING` versus `WITH CHECK`, `FORCE` versus plain `ENABLE`, and the precise predicate are all things where a one-word difference is the whole control.

## Problem Statement

What migration technology does Aaroh commit to, such that security-relevant DDL is directly reviewable and the I-5 governance check is reliable rather than incidentally correct?

## Alternatives Considered

**Option A — Alembic (SQLAlchemy) migrations.**
Rejected as the primary mechanism. Strong for ORM-driven schemas: autogenerate diffs models against the database and produce migrations automatically, which is a genuine productivity gain on large schemas. But three problems here. It defeats the I-5 check as described above. It cannot express RLS policies in its DSL at all — policies would be written as `op.execute("CREATE POLICY ...")`, i.e. raw SQL embedded inside Python, which is the worst of both worlds: opaque to the checker *and* still raw SQL for the reviewer. And autogenerate has no concept of RLS, so it will never notice a missing policy and may generate migrations that drop one. Aaroh also has no existing SQLAlchemy models to autogenerate *from* — the usual justification does not yet apply.

**Option B — Raw SQL migrations, applied by the Supabase CLI.**
**Accepted.** Migrations are `.sql` files under `supabase/migrations/`, timestamp-ordered, applied by `supabase db push`. It is Supabase's native mechanism, so local-to-remote workflow, migration history, and project linking are all handled. Security DDL is reviewed as the literal SQL that will execute. The I-5 check reads exactly what runs.

**Option C — Hybrid: Alembic for tables, raw SQL for policies.**
Rejected. Splits one atomic security requirement across two tools and two files, which directly contradicts I-5's "in the same migration that creates the table". It also creates ordering hazards: a table created by Alembic exists, unprotected, until the policy migration runs. That window is precisely the exposure I-5 exists to prevent.

**Option D — Declarative schema tooling (Atlas, Sqitch, schema diffing).**
Rejected for now. Some handle RLS, and a declarative desired-state model is genuinely attractive for exactly this problem. But each adds a tool to learn and operate for a solo engineer, and none is native to Supabase. Revisit if hand-written SQL migrations become a bottleneck — which, at Aaroh's schema size, they will not for a long time.

**Option E — Supabase dashboard / SQL editor changes.**
Rejected outright. Untracked, unreviewed, unreproducible, invisible to CI, and impossible to apply consistently across environments. Explicitly prohibited below.

## Decision

### 1. Raw SQL migrations under `supabase/migrations/`

Aaroh uses **raw SQL migrations applied by the Supabase CLI**. Files are timestamp-prefixed, committed to the repository, and are the single source of truth for schema state.

**All RLS-sensitive DDL is raw SQL. This is mandatory, not stylistic.** RLS-sensitive DDL means: creating or altering a table holding user data; enabling, forcing, or altering row-level security; creating, altering, or dropping a policy; granting or revoking privileges; creating a `SECURITY DEFINER` function.

Python-generated migrations are prohibited for this DDL because they defeat I-5 (`check_rls_migrations` fails a migrations directory containing DDL-generating Python).

### 2. Every migration is forward-only in deployed environments

A defective migration is corrected by a new migration, never by editing or reverting an applied one. `ADR-0061` already establishes that reverting a *security* migration can re-open access; this generalises the rule to all schema change, because a down-migration that has never been executed is untested code running in an incident.

### 3. Schema changes never bypass the repository

Changes made through the Supabase dashboard SQL editor are prohibited in any environment that holds real user data. A change that is not in `supabase/migrations/` does not exist: it will not reach production, will not survive a project rebuild, and will not be reviewed. The dashboard is for inspection.

### 4. This ADR does not choose the query layer

Migrations own the schema; the application's query mechanism is a separate concern, decided when the first query is written. Rejecting Alembic here does **not** reject SQLAlchemy for queries — the two are separable, and this ADR takes no position on the latter.

### 5. The check is tool-aware, not merely text-matching

`check_rls_migrations` does two things: it asserts that table-creating SQL migrations carry `ENABLE`, `FORCE`, `CREATE POLICY`, and `WITH CHECK`; and it **fails on the presence of DDL-generating Python in the migrations tree**, naming this ADR. The check therefore detects the condition that would blind it, rather than silently passing.

## Security Invariants

Extends `ADR-0061`'s set:

| ID | Invariant |
|----|-----------|
| **I-13** | RLS-sensitive DDL is expressed as raw SQL in `supabase/migrations/`, never generated by application code at migration time. |
| **I-14** | Schema changes are never applied outside the committed migration history. |

## Threat Model

| # | Threat | Mitigation | Residual risk |
|---|--------|-----------|---------------|
| M1 | Table ships with no RLS because the check could not read the migration | Raw SQL mandated; Python DDL in the migrations tree fails CI (I-13) | Low |
| M2 | Policy reviewed as generated code, subtle predicate error missed | Reviewer reads the exact executing SQL | Low |
| M3 | Undocumented dashboard change diverges environments | I-14; migration history is the source of truth | Moderate — this is a *procedural* control with no technical enforcement. See Failure Modes |
| M4 | Down-migration re-opens access during an incident | Forward-only in deployed environments | Low |
| M5 | Migration credential leak | Handled by `ADR-0061` I-11 credential separation and rotation | Accepted, per ADR-0061 T2 |

## Failure Modes

| Failure | Cause | Detection | Recovery |
|---------|-------|-----------|---------|
| Unprotected table in production | Migration merged without RLS statements | `check_rls_migrations` (I-5) | Forward migration adding RLS; audit access logs for the exposure window |
| Governance check silently inert | Migration approach changed to generated DDL | The check fails on Python DDL in the tree (I-13) | Revert to raw SQL, or supersede this ADR deliberately |
| Environments diverge | Dashboard edit not captured in a migration | **Weak.** Drift detection is not yet automated | Diff schema against migration history; codify the difference as a migration |
| Migration applies in dev, fails in prod | Environment-specific state | Apply to `aaroh-dev` first (ADR-0061 I-11) | Forward-fix |

**M3/drift is the honest weak point of this ADR.** Nothing technically prevents someone opening the Supabase SQL editor. A scheduled schema-drift check comparing the live schema against migration history is the correct mitigation and is deferred until there is a schema to drift — but it should not be deferred past the first production deployment.

## Testing Strategy

1. `check_rls_migrations` asserts `ENABLE` + `FORCE` + `CREATE POLICY` + `WITH CHECK` on every table-creating migration, and fails on `DISABLE ROW LEVEL SECURITY` (verified against both a compliant and a non-compliant fixture).
2. The same check fails when the migrations tree contains DDL-generating Python (I-13), verified with an Alembic-style fixture.
3. Migrations are applied to a clean PostgreSQL instance in CI as the precondition for `ADR-0061`'s Tier B RLS suite; a migration that does not apply cleanly fails before any test runs.
4. Structural assertions from `ADR-0061` — every table has RLS enabled *and forced*, with `USING` and `WITH CHECK` — run against the migrated schema, covering tables that do not yet exist.

## Operational Implications

- Supabase CLI becomes a development dependency. Migrations are authored by hand, which is slower than autogenerate and is the intended trade: security DDL should be deliberate.
- Migrations apply to `aaroh-dev` first, then production, using the credential separation in `ADR-0061` I-11.
- CI applies migrations to a throwaway PostgreSQL instance on every PR, so a broken migration fails at review rather than at deploy.
- Hand-written SQL means schema documentation must be generated or maintained rather than inferred from ORM models. Accepted at Aaroh's schema size.

## Rollback / Reversal Strategy

- **Schema:** forward-only. A defective migration is superseded by a new one. Down-migrations are not written for deployed changes; `ADR-0061`'s prohibition on reverting security migrations is the stricter case of this rule.
- **This decision:** adopting a different migration technology requires a superseding ADR that states how I-5 remains enforceable under it. Any such proposal must ship the updated governance check *in the same PR* — the check may not lag the tool, because the window between them is exactly when an unprotected table ships.
- **Code-level:** the rollback target is the preceding release tag per `docs/ENGINEERING_WORKFLOW.md`. Reverting application code does not revert applied migrations.

## Consequences

- The I-5 check is reliable by construction rather than by coincidence, and announces its own blind spot if the approach changes.
- Security DDL is reviewed as the exact SQL that executes.
- Cost: no autogenerate. Every column is hand-written. At Aaroh's expected schema — on the order of twenty tables — this is a modest, one-time-per-table cost against a permanent review benefit.
- Aaroh takes a development-time dependency on the Supabase CLI.
- Schema drift from out-of-band changes remains procedurally, not technically, controlled until drift detection is built.

## Verification Approach

- `check_rls_migrations` passes on a compliant fixture and fails on both a non-compliant SQL fixture and a Python-DDL fixture.
- No `.py` file in `supabase/migrations/` generates DDL.
- Every merged schema change is traceable to a committed migration file.
