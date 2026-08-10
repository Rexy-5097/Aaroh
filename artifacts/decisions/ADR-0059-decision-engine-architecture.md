---
id: ART-ADR-0059
title: "Deterministic Decision Engine Architecture"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-10
modified: 2026-08-10
related_adr: ADR-0058
related_standard: standards/decision_engine.md
related_checklist: QG-009
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0059

> **Status:** Accepted | **Date:** 2026-08-10 | **Decider:** Rexy-5097

## Context

Aaroh's core claim is that a **deterministic engine decides** and an **LLM only explains**. Everything defensible about the product rests on that boundary holding. Aaroh must serve iOS, Android, and Web from one consistent ranking.

The prior specification was internally contradictory: its package diagram placed `decision-engine/` in a shared TypeScript `packages/` directory ("written once, tested once, identical on every platform") while also specifying a FastAPI backend. Two plausible canonical homes were described. This ADR resolves that.

## Problem Statement

Where does the canonical implementation of the ranking and scoring logic live, and what contract keeps it deterministic, testable, and impossible for the LLM to influence?

## Alternatives Considered

- **Option A — Shared TypeScript core in `packages/`, executed on clients.** Rejected, for four reasons:
  1. **It does not actually deliver determinism.** The same TS package executes on JavaScriptCore (iOS), Hermes (React Native), V8 (web), and the system WebView. Floating-point summation order, `Intl` collation, `Date` parsing, and timezone handling genuinely differ across these. The result is code reuse plus *four runtimes to verify* — the opposite of the goal.
  2. **It breaks the audit guarantee.** A client-computed trace is attacker-controlled. Decision Accuracy and Fusion Score — the two metrics the product thesis rests on — would be self-reported by an untrusted client, and score gaming would be trivial.
  3. **Ranking needs server-side state anyway**: DSA history, resume analysis, and prior recommendation outcomes. Client-side ranking means shipping the user's entire state to the device on every rank.
  4. **Language split.** The engine in TypeScript and the backend in Python means either the backend shells out to Node, or reimplements the logic — both violate "one canonical implementation."
- **Option B — Language-neutral specification with a canonical backend implementation.** Rejected as premature. The right instinct, the wrong ceremony for a solo engineer: a formal spec that must stay synchronised with an implementation is a second artifact with no second consumer. Its *discipline* is adopted (purity, weights-as-data, golden files) without its overhead. Revisit only if a genuine second implementation is ever required.
- **Option C — Canonical implementation in the Python backend as a pure package.** **Accepted.**
- **Option D — Engine in the database (SQL/PLpgSQL).** Rejected. Untestable, unversionable, and unportable in practice.

## Decision Rationale

The canonical decision engine lives in the **Python backend**, implemented as a **pure package**.

### Conceptual contract

```
rank(snapshot, constraints, catalog) -> RankedResult
```

Inputs are explicit and complete. Output is fully determined by the inputs.

### Prohibitions — structural, not conventional

The decision engine package MUST NOT:

- access the database directly
- perform network requests
- call an LLM, or import any AI provider SDK
- import Aaroh's AI gateway
- depend on wall-clock time (`now()` is an *input*, never read internally)
- read environment variables or configuration files at runtime
- mutate any external state
- use unseeded randomness

Purity is what makes "the LLM never decides" **structurally enforceable** rather than a stated convention: the package cannot import the gateway, so no code path exists through which an LLM could influence ranking. This is mechanically checkable, and QG-009 checks it.

### The boundary

```
Decision Engine  →  decides
LLM              →  explains
```

The LLM has no authority over ranking, score calculation, weights, recommendation selection, confidence calculation, or state transitions. It receives an already-computed result and renders prose. Explanation is generated **template-first**; the LLM improves wording only. An AI provider outage degrades tone, never function.

### Clients

Clients contain **no second copy of the ranking algorithm**. They receive, via the backend API: recommendation, ranking, score, confidence, explanation trace, `engine_version`, and `weights_version`.

Shared TypeScript packages remain valuable for **types and the API client — not logic**. Client-side presentation formatting of an already-computed result is not business logic and is permitted.

## Consequences

- One implementation, one test suite, one place to fix a ranking bug.
- Every recommendation is computed and persisted server-side, making the audit trail trustworthy and Decision Accuracy measurable against data the client cannot forge.
- **Ranking requires connectivity.** Aaroh has no stated offline requirement, and the Daily Mission is a once-daily server-generated artifact, so this is accepted. If offline ranking is ever required, this ADR must be superseded — not worked around by adding client-side ranking.
- The engine is unit-testable with no database, network, or fixtures beyond plain data.
- Engine purity must be enforced continuously; a single convenience import of a DB session would silently void the guarantee. Hence QG-009 and `standards/decision_engine.md`.

## Verification Approach

- Static check: the decision-engine package imports no database, network, or AI module (enforced at QG-009; governance scenarios VS-025/VS-026).
- Determinism test: identical input snapshots produce byte-identical `RankedResult` across repeated runs and processes.
- No client codebase contains ranking or scoring arithmetic.
- Every persisted recommendation carries `engine_version` and `weights_version`.
