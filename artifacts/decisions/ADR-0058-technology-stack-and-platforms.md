---
id: ART-ADR-0058
title: "Technology Stack and Target Platforms"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-10
modified: 2026-08-10
related_adr: ADR-0059
related_standard: standards/api_design.md
related_checklist: QG-002
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0058

> **Status:** Accepted | **Date:** 2026-08-10 | **Decider:** Rexy-5097

## Context

`PROJECT_CONFIG.yaml` carried `framework: UNDECIDED` and `languages: [UNDECIDED]`. Aaroh must eventually run on iOS, Android, Web, and possibly desktop, and is built by a single engineer on a MacBook Air M4 (16 GB RAM, 256 GB internal SSD, 1 TB external SSD).

The prior product specification (*CareerOS System Design v1.0*, now superseded in name only — see "Canonical name" below) proposed a stack. This ADR ratifies it with three deliberate changes arising from the architecture review.

**Canonical name.** The product is **Aaroh**. *CareerOS* is the previous working name and appears in the v1.0 System Design PDF, which remains the substantive product specification. Vendored AgentOS framework material is not rewritten for the rename.

## Problem Statement

Which technologies does Aaroh commit to for Stages 0–3, and which are explicitly deferred, such that the architecture stays buildable and operable by one engineer on 16 GB of RAM?

## Alternatives Considered

- **Option A — Flutter (single codebase, all platforms).** Rejected. Would deliver genuinely shared UI, unlike the chosen stack. Rejected because it discards existing TypeScript fluency, requires Dart, and does not share a language with the backend or the web ecosystem. The cost of the language switch outweighs the UI-sharing gain for a solo engineer.
- **Option B — Native iOS + Android + separate web.** Rejected. Three codebases, three languages, one engineer. Not tractable.
- **Option C — React Native (Expo) + Next.js + FastAPI + Supabase.** **Accepted.** One language across all clients, cloud builds avoid a local Xcode install, managed backend services avoid local infrastructure.
- **Option D — Node/TypeScript backend instead of Python.** Rejected. Would unify the language end to end, but the deterministic decision engine is canonically Python (ADR-0059), and Python's testing and data-handling ergonomics suit the engine better.
- **Option E — Self-hosted Postgres instead of Supabase.** Rejected for Stages 0–3. Row-Level Security would have to be built and operated by hand; auth and storage would be additional builds. Revisited when scale or cost justifies it.

## Decision Rationale

### Ratified stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Mobile | Expo + React Native + TypeScript | EAS cloud builds; avoids a local Xcode install (~40 GB) on a 256 GB drive |
| Web | Next.js + TypeScript | Shares types and API client with mobile; **not** shared UI components |
| Desktop | **Deferred** | Tauri is not built initially. Revisited only after web/mobile demonstrate demand |
| Backend | Python + FastAPI | Modular monolith; hosts the canonical decision engine |
| Database | Supabase PostgreSQL | Native Row-Level Security |
| Auth | Supabase Auth | Single auth system; no second session layer |
| Storage | Supabase Storage | Private buckets, short-lived signed URLs |
| CI/CD | GitHub Actions | Tests, lint, type check, secret scanning |
| Analytics | PostHog | Pseudonymous identifiers only |
| Errors | Sentry | |
| JS packages | pnpm | Content-addressed store — materially fewer files than npm on external storage |
| Python packaging | Not yet locked | Deliberately deferred; see below |

### Architecture style

**Modular monolith.** Explicitly excluded: microservices, Kubernetes, Redis, and any background-job infrastructure, until a concrete requirement appears. Version numbers are **not** pinned here; they are established at Stage 0 against actual compatibility, not asserted from memory.

### Three changes from the prior specification

1. **Desktop/Tauri is deferred**, not merely sequenced last. Wrapping the Next.js build in Tauri gains little over an installable PWA. Tauri is justified only by a real OS-integration requirement.
2. **Web is not a "near-free add."** React Native primitives are not DOM elements; NativeWind and Next.js do not share a rendering layer. Types, API client, and validation are shared; **screens are written twice**. Web is budgeted at roughly 60–70% of mobile UI effort.
3. **No local PostgreSQL container.** Development uses a managed Supabase development project. This saves ~2 GB of RAM and — more importantly — a local Postgres would not reproduce Supabase's RLS and JWT behaviour, meaning the security model under test would differ from the one shipped.

### Deliberately not decided here

Python dependency tooling (pip/uv/Poetry) is not locked. The repository currently uses `python3 -m venv` plus `tools/requirements.txt` for the AgentOS toolchain, which is sufficient. The application's tooling is chosen when application dependencies actually exist. Also excluded from this ADR: the AI provider (own ADR), RLS implementation specifics (own ADR), and the database schema (own ADR).

## Consequences

- `PROJECT_CONFIG.yaml` moves from `UNDECIDED` to the ratified values, unblocking stack-dependent governance.
- Aaroh takes a hard dependency on Supabase for database, auth, and storage. Postgres portability limits the blast radius; auth and storage migration would be real work. Accepted for Stages 0–3.
- Expo/EAS is a dependency for iOS builds. Acceptable: it is what removes Xcode from the critical path on a 256 GB machine.
- Duplicated UI work between mobile and web is a known, budgeted cost, not a surprise.
- The **9-week** timeline in the prior specification is not ratified. 16–20 weeks is the working estimate; Stage 0 alone is 4–6 weeks for one engineer.

## Verification Approach

- `PROJECT_CONFIG.yaml` contains no `UNDECIDED` framework or language values.
- `context/tech_stack.md` reflects this table and cites this ADR.
- No Redis, message broker, container orchestration, or desktop shell appears in any Stage 0–2 dependency manifest.
- No local PostgreSQL service appears in the development setup.
