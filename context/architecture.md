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

> *One paragraph: what this system does and its primary architectural style.*

[Describe the system in 2–4 sentences: its purpose, its key boundaries, and the architectural style (e.g., microservices, monolith, event-driven, ML pipeline, scientific compute cluster).]

---

## Component Map

```
[Draw an ASCII component diagram here. Example:]

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   API Layer  │────▶│   Database   │
│  (React SPA) │     │  (FastAPI)   │     │  (Postgres)  │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────▼───────┐
                     │  ML Service  │
                     │  (PyTorch)   │
                     └──────────────┘
```

---

## Components

| Component | Responsibility | Technology | Owner |
|-----------|---------------|-----------|-------|
| [Name] | [Single responsibility] | [Tech — see tech_stack.md] | [Team/Person] |
| [Name] | | | |

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
