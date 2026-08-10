# Quality Gate: QG-009 Decision Engine Change

> **Gate ID:** QG-009 | **Version:** 1.0 (Aaroh-specific, additive to AgentOS 1.x)
> **Owner:** `chief-architect` | **Participating Agents:** `qa-reviewer`
> **Estimated Runtime:** 15 min | **Gate Severity:** Mandatory
> **Automation Level:** Semi-automatic | **Retry Policy:** Allowed (Max 2 retries, escalates to chief-architect)
> **Required Context:** `standards/decision_engine.md` · `standards/testing.md`
> **Authority:** `ADR-0059` · `ADR-0060`

---

## Purpose

Protect the determinism, purity, and traceability of Aaroh's decision engine. Any change to ranking, scoring, confidence, candidate generation, weight sets, or the decision trace passes this gate.

## Entry Criteria

- The change touches the decision-engine package, a weight file, or the decision-trace schema.
- Golden-file suite runs and its result is available.

---

## Verification Checklist

| Requirement | Verification Method | Evidence Required | Pass Condition |
|-------------|---------------------|-------------------|----------------|
| **Purity preserved** | Static import scan of the engine package | No DB, network, LLM, gateway, clock, env, or unseeded-random imports | YES (0 violations) |
| **No inline coefficients** | Review engine diff | All ranking numbers reside in versioned weight files | YES |
| **Weight provenance** | Review weight file header | Author, date, basis, and revising evidence stated | YES |
| **Golden files reviewed** | Review golden-file diff | Diff reviewed as content, not auto-regenerated | YES |
| **Determinism** | Repeat-run equality test | Identical input yields byte-identical output across processes | YES |
| **Trace completeness** | Inspect persisted trace | engine_version, weights_version, inputs, constraints, full candidate set | YES |
| **No LLM influence** | Trace data-flow into ranking | No model output reaches score, ranking, weight, or confidence fields | YES (0 paths) |

---

## Exit Decision Model

- **PASS:** Purity intact, weights externalised with provenance, golden diffs reviewed, determinism verified, trace complete. Score = 100.
- **PASS WITH WARNINGS:** All hard requirements met; golden coverage incomplete for a non-primary path with a scheduled follow-up. Score = 80–99.
- **FAIL:** Any prohibited import, any inline coefficient, auto-regenerated golden files, non-deterministic output, incomplete trace, or any path by which model output influences ranking. Score < 80.

---

## Escalation Paths

- **Purity Violation:** Fail the gate and revert the import. If the change genuinely requires external data, escalate to `chief-architect` to redesign it as an explicit engine input.
- **LLM Influence Detected:** Automatic fail, never a conditional pass. Escalate to `chief-architect` — this violates `ADR-0059`.
- **Unexplained Golden Diff:** If expected outputs changed without an intended model change, treat as a defect and fail pending root-cause analysis.
