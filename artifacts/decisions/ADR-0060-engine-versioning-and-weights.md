---
id: ART-ADR-0060
title: "Engine Versioning, Weights-as-Data, and Decision Traceability"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-10
modified: 2026-08-10
related_adr: ADR-0059
related_standard: standards/decision_engine.md
related_checklist: QG-009
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0060

> **Status:** Accepted | **Date:** 2026-08-10 | **Decider:** Rexy-5097

## Context

Aaroh ranks preparation tasks by estimated readiness gain per unit time. Every coefficient in that calculation is, today, **a hypothesis with no supporting evidence**. No usage data exists. No outcome data exists. The product's own governing principles forbid fabricating coefficients or claiming validated optimisation.

Two failure modes follow if this is handled casually:

1. **Magic numbers in code.** Weights buried in source are invisible in review, impossible to audit, and cannot be varied per user or rolled back independently of a code deploy.
2. **Silent score movement.** If a weight changes and every user's score shifts overnight, the transparency work is wasted — users conclude the number is arbitrary. Trust is the product; unexplained score movement is the fastest way to lose it.

## Problem Statement

How are engine weights represented, versioned, and changed, such that (a) no weight is a hidden magic number, (b) any weight change is visible in review, and (c) any historical recommendation can be reproduced and explained?

## Alternatives Considered

- **Option A — Constants in Python source.** Rejected. Invisible in diff review beyond the raw number; couples a model change to a code deploy; cannot pin a user to an older model.
- **Option B — Weights in the database, editable at runtime.** Rejected for now. Attractive for experimentation, but makes the engine's behaviour depend on mutable external state — directly contradicting the purity contract in ADR-0059 — and makes reproduction dependent on a database point-in-time. Revisit only with immutable, versioned rows.
- **Option C — Versioned weight files loaded as data, passed into the engine.** **Accepted.**
- **Option D — Learned weights from usage data.** Rejected as premature. There is no data. This is the Year-2 direction, gated on real Decision Accuracy evidence, and would require its own ADR.

## Decision Rationale

### Weights are data, not code

```
engine/
    weights/
        v1.yaml
```

Weight sets are versioned files. They are **loaded by the caller and passed into** the engine as part of its explicit inputs — the engine itself performs no file I/O, preserving ADR-0059's purity contract.

**No weights are defined by this ADR.** The initial weight values are an explicit, separate future product decision. This ADR establishes only the architectural contract.

### Every weight is a hypothesis

Each weight set carries provenance: who set it, when, on what basis, and what evidence would revise it. Until Decision Accuracy data exists, the honest basis is "judgement, unvalidated" — and it must say so. Aaroh may not describe its ranking as validated or optimised until evidence supports the claim.

### Traceability contract

Every recommendation Aaroh produces must be reproducible from stored data. The persisted decision trace records:

| Field | Purpose |
|-------|---------|
| `engine_version` | which algorithm produced this |
| `weights_version` | which weight set was applied |
| input snapshot | readiness state at decision time |
| constraints | deadline, time budget, target role |
| candidate task set | what was considered, not only what won |
| ranking output | scores and ordering for all candidates |
| contributing sources | which inputs materially affected the result (Fusion Score) |

This must answer, months later and exactly: **"Why did Aaroh recommend this?"** Storing only the winning task is insufficient — the rejected candidates are what make the answer meaningful.

The trace, not LLM prose, is the record of reasoning. Generated explanation text is a rendering of the trace and is never the authoritative reason.

### Golden-file tests

```
input fixture  →  decision engine  →  expected ranking
```

Expected outputs are committed. A weight change that alters any ranking shows up as a **diff in expected output during review**. A change that alters nothing is visibly a no-op. This is the mechanism that makes "every weight is a hypothesis" operationally true rather than aspirational: you cannot change the model without the review showing exactly whose recommendations change.

Golden files must be regenerated deliberately and reviewed as content, never refreshed automatically to make a build pass.

### Score stability

Users are pinned to a `weights_version`. Migration to a new weight set is explicit and, when it moves a user's visible score, surfaced in the UI as a model update rather than presented as earned progress. Mechanism to be specified alongside the score model.

## Consequences

- Weight changes become reviewable product decisions with visible blast radius, rather than invisible code edits.
- Historical recommendations remain reproducible and re-rankable — a prerequisite for measuring whether Aaroh's advice improves over time.
- Cost: golden fixtures must be maintained, and every weight change requires regenerating and reviewing them. This is the intended friction.
- Cost: storing full candidate sets per recommendation is more data than storing the winner. At alpha and beta scale this is negligible, and it is the data the moat argument depends on.
- The engine gains an explicit `weights` input parameter — slightly more verbose call sites, in exchange for testability and purity.

## Verification Approach

- No numeric ranking coefficient appears in decision-engine source; all live in versioned weight files.
- The engine performs no file or environment access to obtain weights.
- A golden-file test suite exists; CI fails when engine output diverges from committed expectations.
- Every persisted recommendation carries `engine_version`, `weights_version`, and the full candidate set.
- A stored trace can be replayed at its pinned versions to reproduce the original ranking exactly.
