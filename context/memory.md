# Project Memory — AI Context Buffer

> **Owner:** All agents append · Project Lead curates
> **Consumers:** All agents — conditional read (load when domain context needed)
> **Update Frequency:** When new patterns discovered · When gotchas hit · When conventions set
> **Max Size:** ~1000 tokens — archive entries older than 6 months to `artifacts/`
> **Cross-refs:** `context/state.md` (current tasks) · `context/architecture.md` (design)
> **Anti-patterns:**
> - Don't duplicate `state.md` (state is current; memory is always-true)
> - Don't add single-use facts — only add if it will matter again
> - Don't add implementation details — add patterns and conventions only

---

## Naming Conventions

| Entity | Convention | Example | Notes |
|--------|-----------|---------|-------|
| [File type] | [Pattern] | `example_name.py` | [When to apply] |
| [Variable type] | [Pattern] | `user_session_id` | |
| [API endpoint] | [Pattern] | `/api/v1/resource` | |
| [Database table] | [Pattern] | `user_events` | |
| [Class] | [Pattern] | `DataValidator` | |

---

## Domain Terminology

| Term | Definition | Context |
|------|-----------|---------|
| [Domain term] | [Precise definition] | [Where it appears] |
| [Acronym] | [Expansion + meaning] | |

> Use this table before using domain terms in code or documentation. Consistency prevents bugs.

---

## Architecture Patterns

> Patterns used in THIS project — not general patterns. See `context/architecture.md` for structure.

| Pattern | Where Used | Why |
|---------|-----------|-----|
| [Pattern name] | [Component] | [Reason] |

---

## Important Assumptions

> Assumptions that are not obvious from the architecture or vision.

- **[ASSUMPTION]:** [Statement] — *Verified: [date] or Unverified*
- **[ASSUMPTION]:** [Statement]

---

## Known Gotchas

| Gotcha | Context | Workaround | Discovered |
|--------|---------|-----------|-----------|
| [Surprising behavior] | [Where it occurs] | [How to handle it] | [Date] |

---

## Reusable Decisions

> Micro-decisions made during implementation that should be applied consistently.
> Formal decisions with full rationale belong in `artifacts/decisions/`.

- **[Decision]:** [One-line rule] — e.g., *"Always validate at the service boundary, not in the controller"*
- **[Decision]:** [One-line rule]

---

## Active Experiments

> Experiments currently running that affect the codebase. Full logs in `artifacts/experiments/`.

| ID | Description | Started | Expected End |
|----|------------|---------|-------------|
| [EXP-YYYY-MM-DD-slug](../artifacts/experiments/) | [Brief description] | [Date] | [Date] |

---

## Archive Rule

When this file exceeds ~1000 tokens:
1. Move entries older than 6 months to `artifacts/` under a named memory snapshot.
2. Keep only: active conventions, current gotchas, ongoing experiments.
3. Never delete — archive.

---

*Context buffer — add entries here when you discover something that will matter again.*
