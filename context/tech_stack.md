# Technology Stack

> **Owner:** Technical Lead
> **Consumers:** All agents (dependency/infrastructure tasks) · All engineers
> **Update Frequency:** When technologies are added, upgraded, or deprecated
> **Max Size:** ~700 tokens
> **Cross-refs:** `context/architecture.md` (how components use these) · `context/decisions.md` (ADRs for choices)
> **Anti-patterns:**
> - Don't add every library — only core technology choices
> - Don't add version numbers without stating the minimum version
> - Don't duplicate architecture.md — focus on WHY chosen, not where used

---

## Core Stack

> **Versions are deliberately unpinned.** They are established at Stage 0 against
> actual compatibility testing, never asserted from memory (`ADR-0058`).

| Layer | Technology | Version | Purpose | Selected Over | ADR |
|-------|-----------|---------|---------|--------------|-----|
| Backend language | Python | TBD at Stage 0 | Canonical decision engine + API | Node/TypeScript | ADR-0058 |
| Client language | TypeScript | TBD | All client shells | — | ADR-0058 |
| Backend framework | FastAPI | TBD | Modular monolith API | Flask, Django | ADR-0058 |
| Mobile | Expo + React Native | TBD | iOS + Android | Flutter, bare RN, native | ADR-0058 |
| Web | Next.js | TBD | Web + PWA | Remix, Vite SPA | ADR-0058 |
| Desktop | **Deferred** | — | Revisit after web/mobile demand | Tauri, Electron | ADR-0058 |
| Database | Supabase PostgreSQL | TBD | Source of truth; native row isolation | Self-hosted Postgres | ADR-0058 |
| Auth | Supabase Auth | TBD | Single auth system | Custom, Auth0 | ADR-0058 |
| Storage | Supabase Storage | TBD | Private resume storage, signed URLs | S3 | ADR-0058 |
| JS packages | pnpm | TBD | Workspace management | npm, yarn | ADR-0058 |
| Python packaging | **Not yet locked** | — | Decided when app deps exist | pip / uv / Poetry | ADR-0058 |
| Cache / Queue | **None** | — | Excluded until a real requirement appears | Redis, Celery | ADR-0058 |

---

## AI Stack

> Aaroh **trains no models**. It consumes a hosted LLM through a single gateway.
> `standards/ai_ml.md` (training governance) is deliberately not enabled;
> `standards/llm_integration.md` governs this layer instead.

| Component | Technology | Purpose | Notes |
|-----------|-----------|---------|-------|
| AI Gateway | Internal (`ai.execute`) | Sole entry point for all model calls | No module outside it imports a provider SDK |
| Provider | **UNDECIDED** | Extraction + explanation | Own ADR required; must offer schema-constrained output and a written no-training commitment |
| Explanation | Deterministic templates | Renders the decision trace | LLM improves wording only; outage degrades tone, not function |

---

## Infrastructure

| Component | Technology | Purpose | Notes |
|-----------|-----------|---------|-------|
| Container | **Not used in development** | — | No local Postgres container; managed Supabase dev project instead (ADR-0058) |
| Orchestration | **None** | — | No Kubernetes. Modular monolith |
| CI/CD | GitHub Actions | Tests, lint, type check, secret scanning | |
| Analytics | PostHog | Product analytics | Pseudonymous identifiers only |
| Monitoring | Sentry | Crash/error monitoring | |

---

## Development Tools

| Tool | Version | Purpose |
|------|---------|---------|
| [e.g., uv / pip] | | Package management |
| [e.g., ruff] | | Linting |
| [e.g., pytest] | | Testing |
| [e.g., pre-commit] | | Git hooks |

---

## Technology Constraints

> Hard constraints that agents must NOT violate when making implementation suggestions.

| Constraint | Reason | Impact |
|-----------|--------|--------|
| [e.g., Python ≤ 3.12 only] | [Dependency incompatibility] | [Scope of impact] |
| [e.g., No paid APIs in core] | [Cost control] | [Use open alternatives] |

---

## Technology Debt and Planned Changes

| Current | Target | Reason | Timeline |
|---------|--------|--------|---------|
| [Legacy tech] | [Replacement] | [Why migrate] | [When] |

---

## Trade-off Log

> Summary of major trade-offs accepted. Full reasoning in ADRs.

| Choice Made | What Was Sacrificed | Why Acceptable |
|------------|-------------------|----------------|
| [e.g., Monolith over microservices] | [Independent scaling] | [Team too small for operational overhead] |

---

*Tech stack last updated: [DATE]. Version upgrades require updating this file.*
