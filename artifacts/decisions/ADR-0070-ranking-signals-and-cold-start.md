---
id: ART-ADR-0070
title: "V1 Ranking Signals and Cold-Start Ordering"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-12
modified: 2026-08-12
related_adr: ADR-0067
related_standard: standards/decision_engine.md
related_checklist: QG-009
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0070

> **Status:** Accepted | **Date:** 2026-08-12 | **Decider:** Rexy-5097

## 1. Problem

`ADR-0059` fixed the engine's contract and `ADR-0067` built its `snapshot` input, but nothing said **what makes one DSA problem a better next problem than another**. The S2 investigation found the objective already stated in three places and the *signals* stated almost nowhere — one sentence in `ADR-0066`, and nothing at all for the alternatives.

This ADR records what Aaroh's V1 recommender is trying to achieve, which evidence it may use, and what it does for a student who has no history yet. It defines **what the model cares about**, never **how to calculate it**.

Every statement carries its basis:

| Tag | Meaning |
|---|---|
| **[E]** | Existing repository evidence |
| **[P]** | **Confirmed product decision, made now.** Not derived from the repository |
| **[U]** | Deferred, with a named owner |

The distinction matters most in §6. **The foundational ordering recorded there is a product decision taken on 2026-08-12. The repository did not previously contain it, and this ADR does not claim otherwise.**

## 2. Objective

**[E]** Three independent sources state the same objective:

- `context/architecture.md` — *"ranks career-preparation tasks by estimated readiness gain per unit of the user's available time"*
- `context/vision.md` — *"what is the highest-value use of my next 90 minutes"*
- `README.md` — *"which single action produces the most improvement in their situation right now"*

> **Aaroh V1 maximises expected improvement per unit of the student's available time.**

**[E]** This is the *objective*, not a signal. `ADR-0067` §2 already drew that line: *"Counting is a fact. Weakness is an interpretation."* A signal is evidence the engine uses to estimate improvement; the objective is what it is estimating.

## 3. The V1 signal

> **[P] Topic weakness is the sole readiness-improvement signal in V1.**

**[E]** It is also the only signal the repository asks for. `ADR-0066`: *"a topic with many attempts and few solves is precisely the weakness the engine should eventually act on"*, and *"solve-versus-attempt ratios as a weakness signal"*.

**[E]** The snapshot already carries what the signal needs, with no new fields: `TopicStat.solved`, `TopicStat.attempted`, and the same pair per difficulty inside `by_difficulty`.

**[E]** Weakness stays an *engine-side* interpretation. `ADR-0067` §2 forbids the snapshot carrying a `weakness_score`, because *"whatever computed that score would be making the ranking decision — outside the pure package, unversioned, untraced"*. Nothing in this ADR moves judgement into the snapshot.

### 3.1 Explicitly deferred signals

**[P]** Not used in V1, and not to be added without evidence:

| Signal | Why deferred |
|---|---|
| **Recency / retention** | **[U]** `ADR-0066` mentions *"recency and consistency from `occurred_at`"* only as something the rows *support*. No product intent is stated anywhere. `last_practised_at` exists in the snapshot and stays unused by V1 ranking. |
| **Difficulty progression** | **[U]** Zero evidence anywhere — no mention of progression, frontier, or "too easy / too hard". `by_difficulty` exists and stays unused by V1 ranking. |
| **Time totals from `minutes_spent`** | **[U]** Optional data (`ADR-0066` §6), so it is absent for many students. Using it would make ranking quality depend on how diligently a student self-reports. |

**[E]** Starting with one signal is what `ADR-0060` implies rather than merely permits: *"every weight is a hypothesis until usage data validates it."* One signal is one hypothesis to invalidate; four entangled signals are a model nobody can attribute a failure to.

## 4. Deadline and time budget

**[P]** For V1, `deadline` and `weekly_hours` are **mandatory execution preconditions and nothing more.** The engine may not run without them, and **neither applies an additional urgency multiplier to any candidate's rank.**

**[E]** This preserves the existing position rather than extending it. `ADR-0065`: *"No recommendation may exist without a deadline and a time budget"* — stated as a precondition. A search for deadline as a *ranking* factor — urgency, deadline pressure, time-remaining weighting — returns nothing in any Aaroh source.

**[P]** No deadline-pressure coefficient is invented here. If urgency should modulate rank, that is a later decision with its own evidence.

Note the objective is already *per unit of available time* (§2), so time enters the model through the **cost side** — how much of the student's budget a candidate consumes — not through a separate urgency term. The cost model itself is `[U]` (§8).

## 5. Cold start

**[E]** `context/state.md` records the requirement: *"A new user with no resume and no DSA history must still get a useful first session."*

**[E]** The S2 investigation established why this needs its own rule: with zero history every topic has `solved = 0`, `attempted = 0` and `last_practised_at = None`, so **every candidate signal produces a sixteen-way tie.** Topic weakness cannot break it, because there is no evidence of weakness anywhere.

> **[P] When a student's DSA history is empty, topic priority is given by the explicit foundational ordering in §6.**

**[P]** The ordering governs **topic priority only**. It is not a score, not a weight, and not a multiplier applied to anything.

## 6. The foundational ordering

> **[P] CONFIRMED PRODUCT DECISION — 2026-08-12. This ordering was chosen now. It is not repository-derived evidence, and no prior Aaroh document contained it.**

```
 1. arrays
 2. strings
 3. hash-tables
 4. two-pointers
 5. sliding-window
 6. sorting
 7. binary-search
 8. linked-lists
 9. stacks-and-queues
10. recursion-and-backtracking
11. trees
12. heaps
13. graphs
14. greedy
15. dynamic-programming
16. math-and-bit-manipulation
```

**[P]** It carries explicit **pedagogical** meaning: earlier entries are where a student with no history should begin. That is a claim about learning, made deliberately, and it is falsifiable — if evidence later shows a different sequence serves beginners better, this ordering is revised by a superseding decision rather than quietly reordered.

**[E]** It is a valid permutation of the vocabulary: the same sixteen entries as `TOPICS`, no additions, no omissions, no duplicates. Ten of the sixteen sit in different positions from the declaration order, which is the concrete demonstration that the two orderings are independent rather than one being a relabelling of the other.

## 7. Separation from `TOPICS`

This section exists because conflating the two orderings is the specific failure this decision was structured to avoid.

| | `TOPICS` declaration order | Foundational ordering |
|---|---|---|
| **Meaning** | Presentation and determinism only | Pedagogical: where a beginner starts |
| **Stated where** | `app/domain/dsa.py` — *"Order is presentation order"* | This ADR, §6 |
| **Used for** | Rendering a list; fixing snapshot field order so output is byte-identical (`ADR-0067` §6) | Cold-start topic priority |
| **Basis** | **[E]** existing | **[P]** decided now |

**[P] They are independent. Changing one does not implicitly change the other.**

**[E]** Re-using the declaration order as a learning sequence was considered and rejected, because three separate places say that order carries no meaning:

1. `app/domain/dsa.py:26` — *"Order is presentation order."*
2. `ADR-0067` §6 — topics are emitted in declaration order **for determinism**, since dict and set iteration order is a leading cause of non-determinism.
3. `ADR-0069` §6 — *"Ordering is not significant and must not be relied on… treating position as primacy would smuggle a weight into the catalogue."*

Repurposing it would have turned an authoring convenience into a hidden product judgement, invisible in review — the exact failure mode `ADR-0069` names.

**[P]** `TOPICS` is **not** reordered by this ADR. Nothing in `app/domain/dsa.py` changes, so snapshot field order, determinism and every existing test are untouched.

### 7.1 An invariant this creates

**[E→U]** A second ordered list over one vocabulary introduces a drift risk that did not exist before: **if a seventeenth topic is added to `TOPICS` and not to the foundational ordering, cold start silently ignores it.**

The invariant is: *the foundational ordering is a permutation of `TOPICS` — same members, no duplicates, no omissions.*

**No governance check is added here**, because the ordering exists only as this document and a check needs a subject. **[U]** The slice that first represents this ordering in code or data **must** add that check, in both directions, exactly as `ADR-0067` §8 obliged the catalogue to draw its topic tags from the same tuple.

## 8. What this ADR does not decide

**[U]** All of the following remain open and are **not** implied by anything above:

| # | Deferred | Owner |
|---|---|---|
| U1 | The weakness formula — how `solved` and `attempted` combine | Score-model slice |
| U2 | Score scale, range, direction, precision, integer-vs-float | Score-model slice |
| U3 | Time-cost model and per-difficulty duration coefficients | Score-model slice (`ADR-0069` D1) |
| U4 | Weight names, values, provenance format | Score-model slice, under `ADR-0060` |
| U5 | Confidence — meaning, scale, computation | Deferred entirely; no evidence exists |
| U6 | Tie-breaking outside cold start | `E6` |
| U7 | `RankedResult` structure | `E2` |
| U8 | Problem selection *within* a chosen topic, and difficulty selection | Score-model slice |
| U9 | Candidate generation and eligibility | `E2` / score-model |
| U10 | Explanation format | Downstream of the engine (`ADR-0059`) |
| U11 | Whether the foundational ordering also applies to *partially* cold students | Score-model slice |

**U11 is worth naming explicitly**: §5 covers an *empty* history. A student with three activities in one topic is neither cold nor warm, and this ADR does not say what happens there. That boundary belongs with the weakness formula, since it is the formula that decides when evidence becomes sufficient.

## 9. Explicit non-goals

No formula, no weights, no score implementation, no confidence model, no recommendation engine, no `RankedResult`, no catalogue data, no candidate generation, no API, no UI, no AI. No Python, no SQL, no migration, no dependency, no governance check.

## 10. Consequences

- The score-model slice now has a fixed target: estimate improvement per unit time, from one signal, with a defined cold-start fallback. That is a considerably narrower problem than it was.
- Cold start is deterministic at the **topic** level. It is **not yet** deterministic at the **problem** level — U8 remains, and a full cold-start recommendation needs it.
- Aaroh now maintains **two** ordered lists over one vocabulary. §7.1 names the drift risk and assigns the check to the slice that can enforce it.
- Deferring recency and progression means their snapshot fields (`last_practised_at`, `by_difficulty`) are populated but unused by V1 ranking. That is deliberate: the data accumulates from day one, so the evidence needed to justify adding those signals is being collected while V1 runs without them.
- Cost: the foundational ordering is a judgement with no supporting data. It is labelled **[P]**, dated, and falsifiable — the same honesty `ADR-0060` demands of weights, applied to an ordering.

## 11. Verification

Review-only; this ADR ships no code.

- `app/domain/dsa.py` is unchanged, so `TOPICS` order and every existing test are unaffected.
- The ordering in §6 is a permutation of `TOPICS`: verified as identical membership, no duplicates, ten positions differing.
- When the ordering is first represented in code or data, that slice must prove: it is a permutation of `TOPICS` (§7.1), it is not derived from `TOPICS` declaration order, and it appears exactly once as the authoritative product ordering.
