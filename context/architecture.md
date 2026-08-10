# System Architecture

> **Owner:** Chief Architect
> **Consumers:** All agents (architecture-touching tasks) · All engineers
> **Update Frequency:** Architecture changes only — never for implementation details
> **Max Size:** ~800 tokens (≈ 1.5 pages)
> **Cross-refs:** `context/tech_stack.md` (technology choices) · `context/decisions.md` (ADRs)
> **Anti-patterns:**
> - Don't include implementation details — describe WHAT, not HOW
> - Don't describe individual functions or classes
> - Don't duplicate tech_stack.md — reference it

---

## System Overview

Aaroh ranks career-preparation tasks by estimated readiness gain per unit of the user's available time, and surfaces one primary recommendation per day. It is a **modular monolith**: a Python backend holding the canonical deterministic decision engine, with thin TypeScript client shells. The load-bearing boundary is that the **engine decides and the LLM only explains** — the engine is a pure package that cannot import the AI layer, making the boundary structural rather than conventional (`ADR-0059`).

**Stage 0 status: no application code exists.** This document describes the ratified target, not an implemented system.

---

## Component Map

```
┌───────────────┐   ┌───────────────┐        ┌──────────────────┐
│  Mobile shell │   │   Web shell   │        │  Desktop shell   │
│ Expo/RN + TS  │   │  Next.js + TS │        │   DEFERRED       │
└───────┬───────┘   └───────┬───────┘        └──────────────────┘
        │                   │
        │  typed API (OpenAPI-generated types; no ranking logic)
        └─────────┬─────────┘
                  ▼
        ┌─────────────────────────┐
        │   FastAPI  (modular     │
        │   monolith, per-domain) │
        └───┬──────────┬──────────┘
            │          │
            │          ▼                    ┌────────────────────┐
            │   ┌──────────────┐            │   AI Gateway       │
            │   │   Decision   │            │  ai.execute()      │
            │   │    Engine    │  ◀── NO ──▶│  sole provider     │
            │   │ pure package │   IMPORT   │  entry point       │
            │   └──────────────┘            └─────────┬──────────┘
            │    decides                     explains │
            ▼                                         ▼
   ┌──────────────────┐                     ┌──────────────────┐
   │ Supabase         │                     │  LLM provider    │
   │ Postgres/Auth/   │                     │  (UNDECIDED)     │
   │ Storage (RLS)    │                     └──────────────────┘
   └──────────────────┘
```

---

## Components

| Component | Responsibility | Technology | Owner |
|-----------|---------------|-----------|-------|
| Decision engine | Ranking, scoring, confidence — **pure, no I/O** | Python package | Chief Architect |
| Backend API | Domain services, persistence, orchestration | FastAPI | Rexy-5097 |
| AI gateway | Sole entry point for every model call | Python | Rexy-5097 |
| Mobile shell | Presentation only | Expo + React Native | Rexy-5097 |
| Web shell | Presentation only | Next.js | Rexy-5097 |
| Data layer | Source of truth, row isolation, private storage | Supabase | Rexy-5097 |

**Invariant:** no client contains ranking or scoring arithmetic. Clients receive recommendation, ranking, score, confidence, explanation trace, `engine_version`, and `weights_version` from the API (`ADR-0059`, `ADR-0060`).

---

## Data Flow

> Describe data movement between components — not implementation.

```
[Data source] → [Transform] → [Storage] → [Consumer]

Example:
User Request → API Layer (validate) → DB (persist) → ML Service (process) → API Layer (respond)
```

Key data flows:
- **[Flow name]:** [Source] → [Steps] → [Destination]
- **[Flow name]:** [Source] → [Steps] → [Destination]

---

## System Boundaries

| Boundary | Internal | External | Interface |
|---------|---------|---------|---------|
| [System edge] | [What is inside] | [What is outside] | [How they connect] |

---

## Extension Points

> Where the system is designed to grow — informs how agents make architectural recommendations.

| Point | Description | How to Extend |
|-------|------------|--------------|
| [Extension point] | [What can be added here] | [Pattern to follow] |

---

## Integration Points

| Integration | System | Protocol | Auth Method | Owner |
|------------|--------|---------|------------|-------|
| [Name] | [External system] | REST / gRPC / MQ | [Method] | [Team] |

---

## Architectural Rationale

> Why key architectural decisions were made. Full reasoning in ADRs.

| Decision | Rationale | ADR |
|---------|-----------|-----|
| [Architectural choice] | [One-line why] | [ADR-NNNN](../artifacts/decisions/) |

---

## Known Limitations

| Limitation | Impact | Planned Resolution | Timeline |
|-----------|--------|-------------------|---------|
| [Current architectural constraint] | [What it prevents] | [Strategy] | [When] |

---

*Architecture last updated: [DATE]. Significant changes require a new ADR.*
