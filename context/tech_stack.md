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

| Layer | Technology | Version | Purpose | Selected Over | ADR |
|-------|-----------|---------|---------|--------------|-----|
| Language | [e.g., Python] | ≥ 3.11 | [Purpose] | [Alternatives] | [ADR-NNNN] |
| Framework | [e.g., FastAPI] | ≥ 0.110 | [Purpose] | [Flask, Django] | |
| Database | [e.g., PostgreSQL] | ≥ 15 | [Purpose] | [MySQL, SQLite] | |
| Cache | [e.g., Redis] | ≥ 7 | [Purpose] | | |
| Queue | [e.g., Celery + Redis] | | [Purpose] | | |

---

## AI/ML Stack

> Complete this section if the project involves AI, ML, or scientific computing.

| Component | Technology | Version | Purpose | Notes |
|-----------|-----------|---------|---------|-------|
| Framework | [e.g., PyTorch] | ≥ 2.0 | [Training/inference] | [CUDA version required] |
| Data | [e.g., Pandas, Polars] | | [Data processing] | |
| Experiment Tracking | [e.g., MLflow, W&B] | | [Experiment logging] | See `artifacts/experiments/` |
| Model Serving | [e.g., TorchServe, ONNX] | | [Inference] | |

---

## Infrastructure

| Component | Technology | Version | Purpose | Notes |
|-----------|-----------|---------|---------|-------|
| Container | [e.g., Docker] | ≥ 24 | [Containerization] | |
| Orchestration | [e.g., Kubernetes] | | [Deployment] | |
| CI/CD | [e.g., GitHub Actions] | | [Automation] | |
| Cloud | [e.g., GCP, AWS] | | [Hosting] | [Region: ] |
| Monitoring | [e.g., Prometheus + Grafana] | | [Observability] | |

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
