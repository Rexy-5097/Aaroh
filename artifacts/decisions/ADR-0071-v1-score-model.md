---
id: ART-ADR-0071
title: "V1 Score Model: Ordinal Topic Weakness with Equal Candidate Cost"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-12
modified: 2026-08-12
related_adr: ADR-0070
related_standard: standards/decision_engine.md
related_checklist: QG-009
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0071

> **Status:** Accepted | **Date:** 2026-08-12 | **Decider:** Rexy-5097

## 1. Problem

`ADR-0070` fixed the objective and named topic weakness as V1's sole signal, but left the model itself open: *how* weakness is read from counts, how much history is enough to read it, and how a candidate's time cost enters a ranking whose objective is stated **per unit of time**.

The S2 research found the repository silent on all three. `ADR-0066` gives a direction — *"a topic with many attempts and few solves is precisely the weakness the engine should eventually act on"* — and nothing more: no function, no threshold, no scale. `ADR-0060` is blunt about why that silence should not be filled casually: *"Every coefficient in that calculation is, today, a hypothesis with no supporting evidence… The product's own governing principles forbid fabricating coefficients."*

This ADR records three product decisions that close the gap **without inventing a single coefficient**.

| Tag | Meaning |
|---|---|
| **[E]** | Existing repository evidence |
| **[P]** | **Confirmed product decision, made 2026-08-12.** Not repository-derived |
| **[R]** | Recommendation / implementation note, not a decision |
| **[U]** | Deferred, with a named owner |

## 2. Objective, restated

**[E]** *Maximise expected improvement per unit of the student's available time* — `context/architecture.md`, `context/vision.md`, `README.md`, and `ADR-0070` §2.

**[P]** Unchanged by this ADR. §5 records honestly that V1's *implementation* of it is incomplete.

## 3. Weakness (Q1)

> **[P] V1 weakness is topic solve rate. A lower solve rate means a weaker topic. Topics are ordered ordinally; no weakness magnitude is defined.**

**[E]** This is exactly the split `ADR-0067` §2 anticipated: *"A ratio is a judgement wearing arithmetic's clothes: choosing solved÷attempted over solved−attempted is already a model. **The engine computes ratios from counts; the snapshot supplies counts.**"* The snapshot stays factual; the ratio lives in the engine, which is where judgement belongs.

**[P] The denominator is total recorded activity in the topic: `solved + attempted`.**

This must be stated because Aaroh's vocabulary collides with ordinary English. **`attempted` is an outcome *value*** — `ADR-0066`: *"engaged with and not completed"* — so `TopicStat.solved` and `TopicStat.attempted` are **disjoint counts**, not a part and a whole. Read the other way, a student who *solved* ten problems in a topic would have `attempted = 0`, and a rule keyed to `attempted` would rank them as having no evidence at all. Solve rate is therefore `solved ÷ (solved + attempted)`.

### 3.1 Ordinal, not magnitude

**[P]** The model orders topics; it does not claim distances between them. Aaroh may say *"graphs is weaker than trees"* and must not say *"graphs is twice as weak as trees"*.

**[P]** No weakness score, range, scale or coefficient is defined here — and none may be introduced without evidence. Ordinality is what makes that possible: an ordering needs no units, no calibration and no normalisation, so there is nothing to fabricate.

**[R] Implementation note, not a decision.** An ordinal comparison of two solve rates needs no floating-point division: for topics with totals `bₓ, b_y > 0`, `aₓ/bₓ < a_y/b_y` iff `aₓ·b_y < a_y·bₓ`. Integer cross-multiplication preserves the byte-identical determinism `ADR-0059` requires and keeps the engine consistent with the float-free discipline `ADR-0067` adopted for the snapshot. The implementing slice may choose otherwise, provided it proves determinism.

## 4. Evidence sufficiency (Q2)

> **[P] A topic is eligible for weakness ordering only once it has at least 3 recorded activities (`solved + attempted ≥ 3`). Below that, its history is treated as insufficient and the topic falls back to the foundational ordering of `ADR-0070` §6.**

| Recorded activities | Treatment |
|---|---|
| 0 | Foundational ordering |
| 1 | Foundational ordering |
| 2 | Foundational ordering |
| 3 or more | Eligible for solve-rate ordering |

**[P] The threshold of 3 is a V1 product decision taken on 2026-08-12. It was not discovered in the repository, and this ADR does not claim otherwise.** No statistical justification is offered because none exists: there is no usage data against which to calibrate it. It is a deliberate, revisable judgement, and the honest basis is *"judgement, unvalidated"* — the phrase `ADR-0060` requires of every weight until evidence exists.

**[P]** This resolves `ADR-0070` **U11**, the partially-cold student, which `ADR-0070` §8 assigned to this slice. The rule is uniform: *sufficiency is per topic*, so a student may be history-ranked in `arrays` and foundationally-ranked in `graphs` at the same moment. There is no global "cold" or "warm" state.

**[P] Explicitly not adopted:** statistical smoothing, Bayesian priors, shrinkage, confidence intervals, exploration/exploitation. Each would introduce coefficients with no evidence behind them.

## 5. Candidate time cost (Q3)

> **[P] V1 treats every candidate as having equal time cost.**

**[E]** The alternatives were closed off by existing decisions, not by preference. `ADR-0069` §10 rejected a per-item `estimated_minutes` because *"how long a problem takes is a property of the student, not the problem"* and the number would be invented by whoever authored the entry — the same objection `ADR-0066` raised when it made `minutes_spent` optional. `ADR-0060` forbids fabricated coefficients outright. And the one empirical source, `minutes_spent`, is optional data that does not yet exist at useful volume.

**[P] No per-difficulty durations, no topic-specific durations, no time multipliers are defined. None may be introduced in V1.**

### 5.1 The consequence, stated plainly

> **[P] With equal cost for every candidate, V1 does not distinguish candidates by time. The objective divides by a constant, so in V1 "maximise improvement per unit time" reduces in practice to "maximise improvement".**

**Aaroh has not solved the time-optimisation problem, and V1 must not be described as though it has.** This is a temporary approximation adopted because the honest alternative — inventing durations — is worse. It is recorded here so the gap is visible in review rather than discovered later in behaviour.

**[U]** A future empirical time-cost model may be derived from observed `minutes_spent` once enough has accumulated. That is a separate versioned decision under `ADR-0060`, requiring its own evidence, weights and provenance. `ADR-0066` §6 already ensures the data is being collected.

## 6. The V1 model, assembled

**[P]** For each candidate problem, in order:

1. Take the candidate's topic tags (`ADR-0069` §6, drawn from `TOPICS`).
2. A topic with `solved + attempted ≥ 3` is **history-eligible**; its position comes from solve rate, lower first (§3).
3. A topic below the threshold is **insufficiently observed**; its position comes from the foundational ordering (`ADR-0070` §6).
4. Candidate cost is equal, so cost does not affect the ordering (§5).

**[U] How the two orderings interleave is NOT decided here.** When one topic is history-eligible at a 20% solve rate and another is insufficiently observed at foundational position 2, this ADR does not say which ranks first. That is a tie-breaking and output-contract question, and §8 assigns it.

**[U]** Nor does it decide how a candidate with **several** topic tags is ordered — `ADR-0069` §6 permits multiple tags and declares their order insignificant. Both belong to the same downstream decision.

## 7. Compatibility

Checked against every accepted decision; no contradiction found.

| Decision | Relationship |
|---|---|
| `ADR-0059` | Unaffected. Ordinal comparison is deterministic; §3.1 notes an integer-only route to byte-identical output. |
| `ADR-0060` | **Reinforced.** No coefficient is fabricated. The one number here (the threshold, §4) is labelled a product judgement, dated, and marked revisable. |
| `ADR-0066` | Consistent. Uses `solved`/`attempted` with their defined meanings, and §3 resolves the vocabulary collision explicitly. |
| `ADR-0067` | **Endorsed by it.** The snapshot supplies counts; the engine computes the ratio — §2 of that ADR says so in as many words. No snapshot field is added or reinterpreted. |
| `ADR-0069` | Consistent. Requires no catalogue field beyond `topics`, and specifically no duration — which §10 of that ADR rejected. |
| `ADR-0070` | Extends it as instructed. Resolves U11; leaves §6's foundational ordering untouched. |
| `standards/privacy.md` | Unaffected. Solve rate is computed from Medium-class DSA history inside the engine and no new field is stored. |

## 8. What remains before the engine can be built

**[U]** After this ADR, the minimum set is small and specific:

| # | Blocker | Owner |
|---|---|---|
| B1 | **Interleaving history-eligible and insufficiently-observed topics** (§6) — the single most load-bearing remainder | Output-contract slice (`E2`) |
| B2 | **Tie-breaking**: equal solve rates; candidates sharing a topic; multi-tag candidates | `E2` / `E6` |
| B3 | **`RankedResult` shape** — task reference, position, and whether a score value is exposed at all given §3.1's ordinality | `E2` |
| B4 | **Candidate-generation boundary** — full catalogue or pre-filtered set (`ADR-0069` D2) | `E2` |
| B5 | **`catalogue_version` in the trace** — `ADR-0060`'s table omits it and replay needs it (`ADR-0069` §9) | `E6` |
| B6 | **Confidence** — no meaning, scale or formula exists anywhere | Deferred entirely |
| B7 | **Explanation structure** | Downstream of the engine (`ADR-0059`) |
| B8 | **Score-model versioning** — whether this model versions separately from `engine_version` | `ADR-0068` follow-up |
| B9 | **Trace retention** | `E6`, with `standards/privacy.md` |

**B1–B4 are the true gate.** With those four, `rank()` can be specified, implemented as a pure function, and proven with golden files against a small hand-authored catalogue. B5–B9 are needed before a recommendation is *persisted or shown*, not before it can be *computed and tested*.

## 9. Explicit non-goals

No engine, no `score.py`, no `decision_engine` package, no weights file, no catalogue data, no `RankedResult` implementation, no candidate selector, no API route, no migration, no UI, no AI. No coefficient, threshold, range or scale beyond the single product threshold in §4 — which is labelled as such.

## 10. Consequences

- The V1 model is now fully specified as a *product contract*: one signal, one ordering rule, one threshold, one stated approximation. Every number in it is either a count from the snapshot or the threshold in §4.
- **V1 will be simple, and visibly so.** That is the intent: `ADR-0060` warns that describing ranking as validated or optimised without evidence is forbidden, and a model with nothing to overclaim cannot break that rule.
- Cost: because candidate cost is equal (§5), a student with 25 minutes and a student with 3 hours receive the same ordering. Only the *time budget precondition* differs. This is the most visible limitation of V1 and it is deliberate.
- Cost: the threshold in §4 is unvalidated. If 3 proves wrong, it is one line in a decision record — which is exactly why it lives here rather than inside an expression in code.
- The ordinal choice defers the entire score-representation question (`scale`, `range`, `precision`, float-vs-int). If a numeric score is ever needed for display, that becomes its own decision with its own evidence.

## 11. Verification

Review-only; this ADR ships no code. When the model is implemented, that slice must prove:

- A topic with fewer than 3 recorded activities never participates in solve-rate ordering.
- A topic with exactly 3 does.
- Ordering by solve rate is stable and byte-identical across processes and repeated runs.
- The denominator is `solved + attempted`, demonstrated by a case where a topic has zero `attempted` and non-zero `solved`.
- No duration, coefficient or weakness magnitude appears anywhere in the implementation.
- A student with zero history receives the foundational ordering unchanged from `ADR-0070` §6.
