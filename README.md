# Aaroh

> **Know what to do next.**

> **Layer:** Project | **Version:** 0.0.0 | **Stage:** 0 — Pre-Development | **Status:** Initialized
>
> ⚠️ **No application code has been built yet.** This repository currently contains governance and identity files only.

---

## What Aaroh Is

Aaroh is a **transparent, constraint-aware career decision engine**.

It is built for students who have limited preparation time and too many competing options, and who need to know which single action produces the most improvement in their situation right now.

Two words carry the weight of that description:

| Property | What it means for Aaroh |
|----------|-------------------------|
| **Transparent** | Every recommendation must be traceable to the inputs and reasoning that produced it. A student must be able to see *why* Aaroh said what it said. |
| **Constraint-aware** | Recommendations account for the student's real limits — available hours, deadlines, current skill level, and competing commitments — not an idealized schedule. |

---

## What Aaroh Is Not

- **Aaroh is not a score.** The Career Readiness Score is a *transparent measurement* used inside the system. It is an instrument, not the product. Aaroh's output is a decision about what to do next; the score exists to make that decision inspectable.
- **Aaroh is not a course catalogue or a job board.**
- **Aaroh is not an opaque recommender.** A recommendation that cannot be explained is treated as a defect.

---

## Project Stage

| Field | Value |
|-------|-------|
| **Stage** | 0 — Pre-Development |
| **Version** | `0.0.0` (see [VERSION](./VERSION)) |
| **Application code** | None. Not started. |
| **Architecture** | Not yet decided. No platform, language, or framework has been selected. |
| **Dependencies** | None installed. |
| **License** | ⚠️ Pending — not yet selected. See [Licensing](#licensing). |

Stage 0 means the repository exists and is governed, but no product decisions have been made and no implementation has begun. Claims about how Aaroh works internally are deliberately absent from this README until they are decided and recorded.

---

## Governance

This project will be developed under **AgentOS** governance.

AgentOS is a deterministic engineering operating system that separates Workflows (SOPs), Agents (decisions), and Tools (execution), and requires that design precede implementation. Aaroh adopts its conventions for:

- Repository structure and file ownership layers
- Documentation standards
- Architecture Decision Records (ADRs) for every significant decision
- Quality gates and checklists
- Semantic versioning and changelog discipline

The AgentOS framework itself has **not yet been installed** into this repository. Installing and bootstrapping it is the next planned step. Until then, references to AgentOS describe an intended governance model, not a currently active runtime.

Contribution rules that already apply are documented in [CONTRIBUTING.md](./CONTRIBUTING.md).

---

## Repository Contents

Everything currently in this repository is governance and identity. There are no application directories, and none will be created before they hold real code.

| File | Purpose |
|------|---------|
| [README.md](./README.md) | This file — product identity and project stage |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Contribution rules, commit format, PR process |
| [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) | Community standards (Contributor Covenant 2.1) |
| [SECURITY.md](./SECURITY.md) | Vulnerability reporting policy |
| [SUPPORT.md](./SUPPORT.md) | Where to ask questions |
| [VERSION_POLICY.md](./VERSION_POLICY.md) | Semantic versioning rules for this project |
| [CHANGELOG.md](./CHANGELOG.md) | Change history |
| [VERSION](./VERSION) | Current version, plain text |
| [docs/DEVELOPMENT_SETUP.md](./docs/DEVELOPMENT_SETUP.md) | How to clone and set up Aaroh on a fresh machine |
| [.github/](./.github/) | Issue templates, PR template, code ownership, labels |

The AgentOS framework is vendored at the repository root (`AGENTOS.md`, `agents/`, `workflows/`, `standards/`, `checklists/`, `templates/`, `runtime/`, `validation/`, and others). Start with [AGENTOS.md](./AGENTOS.md), and see [docs/DEVELOPMENT_SETUP.md](./docs/DEVELOPMENT_SETUP.md) to get a machine running.

---

## Licensing

**No license has been selected yet.**

Until a `LICENSE` file is added to this repository, no license is granted. The source is publicly visible but **all rights are reserved by default** under standard copyright. Do not assume permission to use, copy, modify, or redistribute this work.

Selecting a license is a tracked open decision and will be recorded as an ADR once AgentOS governance is active.

---

## Status of This Document

This README describes only what is currently true. It deliberately makes no claims about features, performance, accuracy, availability, or timelines, because none of those exist yet. It will be updated as decisions are made and recorded.

---

*Aaroh — Know what to do next.*
