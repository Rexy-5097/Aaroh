---
id: ART-ADR-0072
title: "Ranking Output Contract and the V1 Engine Boundary"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-12
modified: 2026-08-12
related_adr: ADR-0071
related_standard: standards/decision_engine.md
related_checklist: QG-009
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0072

> **Status:** Accepted | **Date:** 2026-08-12 | **Decider:** Rexy-5097

## 1. Problem

`ADR-0071` specified how a topic's weakness is read but left four things open: how history-ranked and foundational topics interleave (B1), how ties break (B2), what `rank()` returns (B3), and whether candidate generation is separate from ranking (B4).

The E2 investigation found that **only B1 was a genuine product decision.** B2 is an engineering choice constrained by a principle, B3 is largely forced by decisions already taken, and B4 is moot for V1. This ADR records B1 as decided and the rest as reasoned consequences, and the engine is implemented alongside it.

| Tag | Meaning |
|---|---|
| **[E]** | Existing repository evidence |
| **[P]** | **Confirmed product decision, 2026-08-12** |
| **[R]** | Engineering choice made here |
| **[I]** | Inference from an existing decision |
| **[U]** | Deferred |

## 2. B1 — Repair-first

> **[P] When a topic has sufficient evidence (`solved + attempted >= 3`), its demonstrated weakness is eligible for ranking and takes precedence over insufficiently observed topics. Within V1, demonstrated weakness therefore takes precedence over foundational position.**

Confirmed 2026-08-12. **Not repository-derived** — the E3/E2 searches found no evidence either way on breadth versus repair.

**Rationale.** `ADR-0070` made topic weakness *the* V1 signal and `ADR-0071` built the entire model on it. Letting an untouched topic outrank a measured weakness would make the signal decorative in exactly the cases where it has data. It also produces the strongest explanation — *"you've solved 1 of 5 in graphs"* — and `README.md` treats a recommendation that cannot be explained as a **defect**.

**Rejected:** foundational-always-first (would strain ADR-0070/0071 by demoting the signal they established), and position-blending (would need a mapping between two incommensurable scales — an invented coefficient, forbidden by `ADR-0060`).

### 2.1 Known limitation: tunnelling

> **[P] Repair-first has no breadth escape mechanism in V1.**

A student who repeatedly struggles with one topic can be shown that topic indefinitely. This is **deliberate and recorded, not overlooked**.

**No exploration coefficient, breadth score, decay factor or escape threshold is introduced to solve it.** Each would be an unvalidated coefficient of exactly the kind `ADR-0060` forbids, and there is no recommendation-outcome data to calibrate one against. A future exploration policy requires evidence — and `ADR-0059` already anticipates the data it would need: *"prior recommendation outcomes"*.

**[U]** Whether V1's tunnelling is acceptable in practice is measurable once recommendations are produced. That is the first thing real usage should tell us.

## 3. B2 — Tie-breaking

**[R]** The governing principle: **a tie-break must not introduce a new learning preference.** A tie means the model is indifferent; resolving it with something *meaningful* would smuggle in a second product judgement nobody reviewed.

The total order, in key order:

| # | Key | Basis |
|---|---|---|
| 1 | Tier: repair before foundational | **[P]** §2 |
| 2 | Within repair: lower solve rate first | **[E]** `ADR-0071` §3 |
| 3 | Foundational position | **[P]** `ADR-0070` §6 — a *declared* preference, used as the fallback for both tiers |
| 4 | `slug` ascending | **[R]** neutral |

**[R] `slug` ascending is an engineering determinism choice, not a learning preference.** It is arbitrary by design: when the model has nothing left to say, the tie is settled by something that encodes no opinion. Slug uniqueness (`ADR-0069` §3, enforced in `validate_catalogue`) makes the order **total**, which `ADR-0059`'s byte-identical requirement demands.

**Explicitly not used:** timestamps, UUIDs, database order, catalogue insertion order, or `TOPICS` declaration order — each is either non-deterministic or carries meaning it should not.

## 4. B3 — What `rank()` returns

**[I] Four fields. Each is forced; nothing is included because it might be useful.**

```
RankedCandidate: slug · position · reason · reason_topic
RankedResult:    candidates (the full ordered set)
```

| Field | Basis |
|---|---|
| `slug` | **[E]** `ADR-0069` §3 — the catalogue's identity |
| `position` | **[E]** ordering *is* the output |
| `reason` | **[E]** forced by `README.md`: an unexplainable recommendation is a defect |
| `reason_topic` | **[I]** a reason code alone cannot be rendered — *"because graphs"* needs the topic |
| full candidate set | **[E]** `ADR-0060`: *"the rejected candidates are what make the answer meaningful"* |

**Deliberately excluded:**

- **`score` — [I] there is none to return.** `ADR-0071` §3.1 made weakness **ordinal with no magnitude**. Inventing a number to expose would breach both that ADR and `ADR-0060`'s ban on fabricated coefficients.
- **`confidence`** — **[U]** no meaning, scale or formula exists anywhere.
- **`engine_version`, `weights_version`, `catalogue_version`** — **[I]** the *caller* already holds these; a pure function restating its own inputs adds nothing. They belong in the trace, assembled outside.
- **Explanation prose** — **[E]** `ADR-0059` places it downstream, template-first.

`ADR-0059`'s list of *"recommendation, ranking, score, confidence, explanation trace, engine_version, weights_version"* sits under a heading titled **"Clients"** and says *"they receive, **via the backend API**"*. That is the **API response**, not the engine's return value. Conflating the two is how a pure function ends up carrying prose and version strings.

### 4.1 Reason codes

**[I]** A closed vocabulary of exactly two values — `weak-topic`, `foundational` — because `ADR-0071`'s model has exactly two states. The vocabulary is *forced by the model*, not invented.

## 5. B4 — Candidate generation

**[I] Not split in V1, because there is nothing to split.**

`standards/decision_engine.md` says *"keep candidate generation separate from ranking"*, and its Scope governs both. But V1 has **no eligibility rule to apply**: the only one ever contemplated — *"don't recommend what they already solved"* — is explicitly deferred by `ADR-0067` §4.3, blocked on catalogue-identity matching (U3), and `ADR-0071` defines no filter either.

So candidate generation would be the identity function. Building the abstraction now would be machinery with no behaviour behind it.

**[R]** The signature stays exactly as `ADR-0060` specifies: `rank(snapshot, constraints, catalog, weights)`. Placement is computed per candidate through `_candidate_placement`, so introducing a filter later is a new step in front of an unchanged ranking algorithm — not a rewrite.

**[R] `weights` is accepted and V1 reads no value from it.** The parameter is present so the first weight set needs no signature change, and `test_weights_cannot_change_the_v1_ordering` proves mechanically that no coefficient has crept in.

## 6. Implementation notes

**[R]** The engine lives at `backend/app/decision_engine/`, which is one of the four paths `check_governance.py` watches. **Naming it anything else would have left the engine purity check ARMED and silently unenforced.** With this slice the check is **active** for the first time.

**[R]** The module is `ranking.py`, not `rank.py`. Re-exporting a function named `rank` from a module named `rank` makes `app.decision_engine.rank` resolve to the *function* and shadow the module — which already caused a purity test to inspect one function's source instead of the file, and pass while a float division sat two functions away. The rename removes the hazard.

**[R]** Solve rates are compared by **integer cross-multiplication**: `a/b < c/d` iff `a·d < c·b` for positive `b, d`. No float appears in the engine, so cross-platform float behaviour cannot alter an ordering, and Python's arbitrary-precision integers make overflow impossible.

**[R]** The foundational ordering lives in `app/domain/foundational.py`, separate from `TOPICS` in `dsa.py` (`ADR-0070` §7). It **verifies at import** that it is a permutation of `TOPICS` — discharging the obligation `ADR-0070` §7.1 assigned to "the slice that first represents this ordering in code".

**[R]** The catalogue is a **test fixture, not a production artifact**. `ADR-0069` §9 requires a real catalogue to be a versioned file with an immutable label, and `ADR-0068` §8 explicitly deferred the *label format*. Authoring a versioned artifact before its identifier format exists would invent the thing that ADR deferred. The engine takes `catalog` as an explicit input, so it needs no production catalogue to be proven correct.

## 7. Multi-topic candidates

**[I]** A candidate is placed by its **most urgent topic**.

`ADR-0069` §6 permits several tags and declares their order insignificant, so a rule was required. This one follows directly from repair-first: if a problem can address a demonstrated weakness, demoting it because it *also* touches an untouched topic would contradict §2. `reason_topic` reports the topic that actually decided the placement, so the explanation stays truthful.

## 8. Privacy and security

**[E]** The engine is pure and holds no identity. It receives a snapshot already built under the caller's RLS-bound transaction (`ADR-0067` §10) and reads only Medium-class aggregate counts. It **stores nothing, logs nothing, and calls nothing**.

`RankedCandidate` carries no `user_id`, no goal field, no free text and no timestamp — so a result is safe to place in a trace without raising its class. (The trace itself is High-class because `ADR-0060` stores `constraints`; that remains `E6`'s problem, unchanged by this ADR.)

## 9. Non-goals

No API route, no persistence, no trace store, no UI, no AI, no ingestion, no production catalogue artifact, no weights file, no confidence, no exploration policy, no migration, no database change.

## 10. Deferred

| # | Deferred | Owner |
|---|---|---|
| D1 | Breadth/exploration policy for the tunnelling limitation (§2.1) | Needs recommendation-outcome evidence |
| D2 | Eligibility rules, incl. excluding solved problems | Blocked on `ADR-0067` U3 |
| D3 | `catalogue_version` in the trace | `E6` |
| D4 | Confidence | Deferred entirely |
| D5 | Explanation templates | Downstream (`ADR-0059`) |
| D6 | Production catalogue artifact | Blocked on the label format (`ADR-0068` §8) |
| D7 | Trace retention and its privacy class | `E6` |
| D8 | Empirical time-cost model | Needs `minutes_spent` volume (`ADR-0071` §5.1) |

## 11. Verification

- 48 golden tests, each naming the decision that produces its expected order.
- 21 meaningful mutants, all caught; one proven a no-op (a candidate filter cannot drop anything because the snapshot is dense over all sixteen topics, `ADR-0067` §4.1); one negative control that correctly survived.
- Engine purity check **active** — 2 files clean.
- Domain purity — 6 modules pure.
- `test_weights_cannot_change_the_v1_ordering` proves no coefficient exists.
- `test_no_floating_point_appears_in_the_engine` parses the whole module AST and asserts no float literal and no true division.
