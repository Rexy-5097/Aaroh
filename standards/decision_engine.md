# Standard: Deterministic Decision Engine

> **Tier:** Domain — applies to Aaroh's ranking and scoring core
> **Owner:** Chief Architect | **Reviewer:** `chief-architect` · `qa-reviewer`
> **Consumers:** `chief-architect` · `qa-reviewer` · `llm-reviewer` (boundary checks) | **Max:** ~1500 tokens
> **Cross-refs:** `standards/testing.md` · `standards/llm_integration.md` · `standards/code_quality.md` · `checklists/decision_engine_change.md`

---

## Purpose

Keep Aaroh's decision engine deterministic, pure, versioned, and reproducible, so that every recommendation can be explained and re-derived from stored data. This standard exists because Aaroh's entire product claim — that a transparent engine decides and an LLM only explains — is void the moment the engine acquires hidden inputs.

## Scope

**Governs:** Ranking, scoring, confidence calculation, candidate generation, weight sets, decision traces, golden-file tests.
**Does NOT govern:** LLM behaviour (→ `standards/llm_integration.md`), data storage and ownership (→ `standards/privacy.md`), API shape (→ `standards/api_design.md`).

**Authority:** `ADR-0059` (architecture), `ADR-0060` (versioning and weights).

---

## Guiding Principles

1. **Same input, same output. Always.** Determinism is a correctness property, not a performance detail.
2. **The engine decides; the LLM explains.** No exceptions, no convenience shortcuts.
3. **Every weight is a hypothesis** until usage data validates it. The engine must never be described as validated or optimised without evidence.
4. **A recommendation that cannot be traced to its inputs is a defect**, not a rough edge.
5. **Purity is enforced structurally**, not by convention. If the package *can* import the AI gateway, someone eventually will.
6. **Rejected candidates are part of the answer.** Storing only the winner destroys the explanation.

---

## Purity Contract

The decision engine package MUST NOT:

| Prohibition | Why |
|-------------|-----|
| Access a database | Hidden input; breaks reproducibility |
| Perform network requests | Hidden input; non-deterministic |
| Call an LLM or import a provider SDK | Voids the decision/explanation boundary |
| Import Aaroh's AI gateway | Same, one layer removed |
| Read wall-clock time | `now()` is an input, never read internally |
| Read env vars or config at runtime | Behaviour becomes environment-dependent |
| Use unseeded randomness | Non-reproducible |
| Mutate external state | Makes call order significant |

Conceptual signature: `rank(snapshot, constraints, catalog, weights) -> RankedResult`. Inputs explicit and complete; output fully determined by inputs.

---

## Quality Levels

| Dimension | Minimum Acceptable | Recommended | Production Grade |
|-----------|-------------------|-------------|-----------------|
| Purity | No DB/network in engine | + no clock, no env, no randomness | Enforced by automated import check in CI |
| Weights | Externalised from code | Versioned files with provenance | + per-user version pinning |
| Traceability | Winning task stored | + inputs and constraints stored | + full candidate set and contributing sources |
| Golden tests | Fixtures exist | Cover the main ranking paths | + boundary and degenerate cases; CI-gated |
| Reproducibility | Repeat run matches | Matches across processes | Historical trace replays exactly at pinned versions |
| Confidence model | Documented | Missing data demonstrably lowers confidence | Confidence calibration reviewed against outcomes |

---

## Best Practices

- **Pass time in.** Every time-dependent value arrives as an explicit parameter.
- **Keep candidate generation separate from ranking.** Two pure steps are easier to test than one.
- **Store the whole candidate set**, with scores, not just the selected recommendation.
- **Record provenance in weight files**: who set them, when, on what basis, and what evidence would revise them. Until evidence exists, the basis is "judgement, unvalidated" — say so.
- **Regenerate golden files deliberately** and review the diff as content. Never auto-refresh to make a build pass.
- **Make confidence fall honestly.** Missing inputs must reduce confidence; never present precision the inputs do not support.
- **Version the engine and the weights independently.** An algorithm change and a coefficient change have different blast radii.

---

## Anti-patterns

| Anti-pattern | Why It Fails |
|-------------|-------------|
| Numeric coefficients inline in ranking code | Invisible in review; cannot be pinned or rolled back independently |
| Engine reads config or DB "just for defaults" | Reintroduces hidden input; reproducibility silently dies |
| Auto-regenerating golden files in CI | Removes the exact signal the tests exist to produce |
| Storing LLM prose as the reason for a recommendation | The audit trail becomes generated text |
| Client-side re-implementation "for responsiveness" | Two sources of truth; client traces are attacker-controlled |
| Calling the engine "optimised" pre-evidence | Overclaiming; contradicts the product's own principles |
| Discarding rejected candidates | "Why this?" becomes unanswerable |

---

## Common Failure Modes

| Failure | Why It Happens | Detection | Recovery |
|---------|---------------|-----------|---------|
| Non-deterministic output | Dict/set iteration order, unseeded randomness, clock read | Repeat-run equality test | Make ordering explicit; pass time in |
| Untraceable recommendation | Trace stored after the fact, partially | Replay test on stored traces | Persist trace atomically with the recommendation |
| Silent score shift | Weight change applied to all users at once | Version pinning + score-history diff | Pin users; surface model updates in UI |
| Purity erosion | One convenience import during a deadline | Automated import check (QG-009) | Revert; add the check if it was missing |

---

## Reviewer Questions

```
DECISION ENGINE REVIEW CHECKLIST
□ Does the engine avoid all DB, network, LLM, and gateway imports?
□ Is wall-clock time passed in rather than read?
□ Is all randomness seeded, or absent?
□ Are all ranking coefficients in versioned weight files, not source?
□ Do weight files carry provenance and an honest evidence basis?
□ Were golden files regenerated and reviewed as content?
□ Does the persisted trace include the full candidate set?
□ Are engine_version and weights_version recorded per recommendation?
□ Does the same input snapshot reproduce byte-identical output?
□ Does missing input data demonstrably lower reported confidence?
```

---

## Completion Criteria

- [ ] Purity check passes (no prohibited imports in the engine package)
- [ ] Golden-file suite passes, or diffs are reviewed and accepted
- [ ] Determinism test passes across repeated runs and processes
- [ ] Trace completeness verified for every new recommendation path
- [ ] `checklists/decision_engine_change.md` (QG-009) completed

---

## Cross-references

| Topic | Standard |
|-------|---------|
| Test taxonomy and coverage | `standards/testing.md` |
| LLM boundary enforcement | `standards/llm_integration.md` |
| Code structure and purity idioms | `standards/code_quality.md` |
| Engine change gate | `checklists/decision_engine_change.md` |
