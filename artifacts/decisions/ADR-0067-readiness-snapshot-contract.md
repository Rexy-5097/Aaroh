---
id: ART-ADR-0067
title: "The Readiness Snapshot Contract"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-11
modified: 2026-08-11
related_adr: ADR-0059
related_standard: standards/decision_engine.md
related_checklist: QG-009
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0067

> **Status:** Accepted | **Date:** 2026-08-11 | **Decider:** Rexy-5097

## Context

`ADR-0059` fixed the engine's shape and `ADR-0060` amended it to carry weights:

```
rank(snapshot, constraints, catalog, weights) -> RankedResult
```

Two of those four inputs now have real sources. `ADR-0065` built `constraints` — *"not a step toward it, the thing itself"* — and `ADR-0066` built the first source of `snapshot` data. Neither defined what `snapshot` **is**. `ADR-0066` §8 said so explicitly and refused to invent one.

That refusal has now expired usefully. Three ADRs describe `snapshot` only in prose — *"the student's current readiness state"* (`ADR-0065`), *"readiness state at decision time"* (`ADR-0060`). No field has ever been named. Every later slice — the readiness score, the catalog, the engine itself — consumes this structure, so it is the next thing that has to exist, and it has to exist **before** anything computes against it.

This ADR defines the contract. It implements nothing.

## Problem Statement

What exactly is the `snapshot` argument — its type, boundary, fields, temporal semantics and missing-data behaviour — such that the engine can be written against it without the engine's design leaking backwards into the data model?

---

## 1. What a snapshot is

> **A snapshot is an immutable, in-memory, point-in-time projection of one student's readiness-relevant state, constructed outside the engine and passed in as plain data.**

Taking the brief's five candidate readings in turn:

| Candidate | Verdict |
|-----------|---------|
| A database projection | **No.** `ADR-0059` forbids the engine touching a database. A projection the engine must query is a hidden input. |
| An in-memory immutable object | **Yes.** This is the accepted form. |
| A point-in-time read model | **Yes, and inseparable from the above.** `as_of` is a field, not context. |
| A serialized structure | **Derivatively.** It must serialise losslessly for `ADR-0060`'s trace, but serialisation is a consequence of being plain immutable data, not its identity. |
| Something else | No. |

It is therefore **both** an immutable object and a point-in-time read model: the object *is* the read model, materialised.

### 1.1 What it is not

**Not a table.** No `snapshots` table is created, now or by this ADR. A snapshot is derived from `dsa_activities`, which is the durable record. Persisting a second copy would create two sources of truth that can disagree, and `ADR-0066` made the activity log append-only precisely so history stays authoritative.

The one place a snapshot *is* persisted is inside a decision trace (`ADR-0060`), where it is stored **as evidence of what the engine saw**, not as state. That copy is immutable by nature: it records a past decision.

**Not a score.** A snapshot carries facts. `Career Readiness Score` is a function *of* a snapshot and lives in the engine. `ADR-0065` rejected building the score first for exactly this reason.

---

## 2. The boundary — where interpretation is not allowed

This is the load-bearing decision of this ADR, and every field choice below follows from it:

> **The snapshot carries facts. The engine carries judgement.**

Counting is a fact. Weakness is an interpretation.

If the snapshot carried a `weakness_score` per topic, whatever computed that score would be making the ranking decision — and it would be doing so *outside* the pure package, unversioned, untraced, and unreachable by `ADR-0060`'s golden files. The engine would be reduced to sorting numbers someone else already decided. That is `ADR-0059`'s boundary failing quietly rather than loudly.

So the rule is mechanical:

| Belongs in the snapshot | Belongs in the engine |
|---|---|
| How many `graphs` problems were attempted | Whether `graphs` is a weakness |
| When `trees` was last practised | How much staleness matters |
| Minutes recorded, and over how many rows | Whether the student is efficient |
| Counts per difficulty | What a `hard` solve is worth |

**No coefficient, threshold, ratio or ranking appears in a snapshot.** A ratio is a judgement wearing arithmetic's clothes: choosing solved÷attempted over solved−attempted is already a model. The engine computes ratios from counts; the snapshot supplies counts.

---

## 3. Inputs

| Source | Supplies | Status |
|--------|----------|--------|
| `public.dsa_activities` (`ADR-0066`) | All DSA fields below | **Available** |
| `app.domain.dsa.TOPICS` | The vocabulary the snapshot is dense over | **Available** |
| The caller | `as_of` | Injected |
| `public.preparation_goals` (`ADR-0065`) | **Nothing** — see §7 | Available, deliberately unused |
| Resume analysis | **Nothing** — no schema exists | Not built |

Aaroh's readiness picture is currently one-dimensional. This ADR says so rather than padding the structure with fields that have no source.

---

## 4. Fields

Structure, not code. Types are Python for precision; nothing here is implemented by this ADR.

```
StudentSnapshot                     (frozen, hashable, ordered)
    subject                 UUID              whose state this is
    as_of                   datetime (UTC)    the decision instant
    vocabulary_version      str               which topic list this is dense over
    dsa                     DsaSnapshot

DsaSnapshot
    total_activities        int               all recorded events, all time
    first_activity_at       datetime | None   None iff total_activities == 0
    last_activity_at        datetime | None   None iff total_activities == 0
    topics                  tuple[TopicStat]  exactly one per vocabulary topic

TopicStat
    topic                   str               a member of TOPICS
    solved                  int
    attempted               int
    by_difficulty           tuple[DifficultyStat]   exactly one per difficulty
    minutes_recorded        int               sum of minutes_spent where present
    activities_with_minutes int               the denominator, stated explicitly
    last_practised_at       datetime | None   None iff this topic is untouched

DifficultyStat
    difficulty              str               easy | medium | hard
    solved                  int
    attempted               int
```

### 4.1 Why the topic list is dense

`topics` contains **all sixteen** vocabulary entries, including those with zero activity — not only the practised ones.

A sparse list forces every consumer to distinguish "absent" from "zero", and they are the same thing here: a topic with no rows *is* a topic practised zero times. Denseness also means the engine never needs the vocabulary itself, so adding a seventeenth topic is a change to `app.domain.dsa` and its snapshot builder, with no engine edit at all.

The cost is that each snapshot restates the vocabulary. That is sixteen small records, and it buys a total function — `snapshot.dsa.topics` can never raise `KeyError`.

`vocabulary_version` is what makes this safe across time: a trace stored when the list had sixteen entries must be replayable as a sixteen-entry snapshot even after a seventeenth is added. Without it, `ADR-0060`'s replay guarantee silently degrades the first time the vocabulary grows.

### 4.2 Why `activities_with_minutes` exists

`minutes_spent` is optional (`ADR-0066` §6). Carrying only `minutes_recorded` would let a consumer divide by `solved + attempted` and produce an average over rows that never had a value — fabricated precision, and exactly what `standards/decision_engine.md` means by *"never present precision the inputs do not support."* Carrying the denominator makes the gap visible instead of invisible.

### 4.3 What is deliberately absent

| Excluded | Why |
|----------|-----|
| `problem_title` | Free text the student typed. The engine has no use for it, and it is the least predictable field in the system. |
| `platform` | Metadata only (`ADR-0066` §7). Ranking on it would make Aaroh's advice platform-dependent — a `Phase 8.9` violation. |
| `problem_ref` | Would enable "don't recommend what they already solved", which is real — but matching refs against a catalog needs a catalog identity scheme, and no catalog exists. See §12. |
| `target_role`, `target_company`, `deadline`, `weekly_hours` | These are `constraints` (§7). |
| Any score, ratio, rank or weakness signal | §2. |
| Any resume field | No source (§3). |

`ADR-0066` set the precedent — *"no speculative fields: unused personal data is a liability"* — and it applies with more force here, because a snapshot is copied into every stored trace.

---

## 5. Temporal semantics

**`as_of` is injected. Always.** `ADR-0059` prohibits the engine reading wall-clock time and `ADR-0065` already applied the same discipline to `today` in the goal domain. This ADR extends it to the snapshot builder: **the builder is also forbidden from reading the clock.** A builder that calls `now()` internally makes snapshots unreproducible, which defeats the trace before the engine is even reached.

The signature carries no `now` parameter, so the decision instant has to live inside one of the four arguments. It belongs to the snapshot, and not by elimination: `ADR-0060` already describes this input as *"readiness state **at decision time**"*. A snapshot without its instant is not a snapshot, it is a query result.

**Inclusion rule:** an activity is included iff `occurred_at <= as_of`.

Today that rule can never exclude anything — `occurred_at` is not client-settable and defaults to `now()` at insert (`backend/app/db/dsa.py`). It is stated anyway, for two reasons. It makes historical replay correct the moment backdated entry is added, and without it, replaying a stored trace after new activity arrives would produce a *different* snapshot from the one recorded — breaking `ADR-0060`'s central promise.

**No aggregation window.** Counts are all-time; recency travels separately as `last_practised_at` and `last_activity_at`.

Choosing a window — "the last 90 days" — would bake a decay decision into the input. Whether ninety-day-old practice still counts is a *model* question, so it belongs in a weight file where it is versioned, reviewable and revisable per `ADR-0060`, not frozen into the data structure where changing it silently rewrites history.

---

## 6. Derived values, and how far derivation goes

Everything below `total_activities` is derived by aggregation over `dsa_activities`. All of it is **counting, extremum, and summation** — operations with no free parameters. That is the test for whether a derivation may live in the snapshot: *if there is a number I could have chosen differently, it does not belong here.*

Deterministic by construction:

- `topics` ordered by `TOPICS` declaration order; `by_difficulty` by `DIFFICULTIES` order.
- Tuples, never sets or dicts — `standards/decision_engine.md` names dict/set iteration order as a top cause of non-determinism.
- No floating-point arithmetic anywhere. Every numeric field is an integer count or sum, so cross-platform float summation order cannot alter a snapshot.

Aggregation happens **in SQL, inside `backend/app/db/`, under RLS**, in a query written for this purpose. It must not reuse `list_activities`, which is bounded at 100 rows — a snapshot built from that path would silently truncate for any active student and produce confidently wrong counts.

Explicitly *not* derived here: solve rates, weighted totals, staleness measures, per-topic strength, or any overall figure. Those are `rank()`'s.

---

## 7. Relationship with `constraints`

The brief asks whether the two are correctly separated. **They are, and the repository already decided it — twice, independently.**

- `ADR-0065` §"Why this one": the preparation goal *"is the `constraints` argument of `ADR-0059`'s contract, directly. Not a step toward it — the thing itself."*
- `ADR-0060`'s trace table: `constraints | deadline, time budget, target role`.

Those two enumerations agree exactly with the columns of `preparation_goals`. There is no ambiguity to resolve, and this ADR resolves none — it records the existing boundary:

| | `snapshot` | `constraints` |
|---|---|---|
| Answers | Where is this student now? | What bounds the answer? |
| Source | `dsa_activities` | `preparation_goals` |
| Changes when | The student practises | The student restates their goal |
| Authored by | Aaroh, from observed facts | The student, as a statement of intent |
| Privacy class | **Medium** | **High** |

The last row is not incidental. `standards/privacy.md` classes DSA history **Medium** and `target_role`/`target_company` **High**. Keeping the goal out of the snapshot keeps the snapshot uniformly Medium — which matters because `ADR-0060` copies the snapshot into every persisted trace. Merging the two would silently promote every trace to High-class, pulling in audit-logging and minimisation obligations the design never intended.

**`days_remaining` is in neither.** It is `constraints.deadline − snapshot.as_of`, computed by the engine from two inputs it already holds. `ADR-0065` reached the same conclusion for the API — *"derived on read, never stored — a stored value would be wrong the next morning"* — and storing it in a snapshot would be the same mistake with a longer half-life, since traces are kept.

Likewise **remaining preparation time** — the hours actually available — is `weekly_hours × (days_remaining ÷ 7)`, a product of two constraint values and `as_of`. The division is a modelling choice about partial weeks, which puts it in the engine.

---

## 8. Relationship with `catalog`

The snapshot describes **the student**; the catalog describes **available tasks**. They are disjoint, and the snapshot must contain no catalog data — a snapshot mentioning specific tasks would mean candidate generation had already happened outside the engine.

They meet at exactly one point: **the topic vocabulary is the join key.** A catalog task tagged `dynamic-programming` is matched to `TopicStat(topic="dynamic-programming")`. That is the whole interface, and it is why `ADR-0066` put the vocabulary in the domain layer rather than in a PostgreSQL enum — both sides can import it as pure data.

This creates one obligation worth naming now: when the catalog is designed, its topic tags must be drawn from the same `TOPICS` tuple. A catalog with its own list would make the join lossy in a way no test would catch until recommendations quietly stopped covering some topics.

---

## 9. Missing-data semantics

> **A snapshot is total. It can always be constructed for any authenticated user.**

| Case | Behaviour |
|------|-----------|
| No DSA activity at all | Valid snapshot. `total_activities = 0`, both timestamps `None`, all sixteen `TopicStat`s present and zeroed. |
| Some topics untouched | Their `TopicStat` is zeroed with `last_practised_at = None`. Untouched is not missing. |
| No `minutes_spent` recorded | `minutes_recorded = 0`, `activities_with_minutes = 0`. Distinguishable from "zero minutes spent". |
| **No preparation goal** | The snapshot is **unaffected** — it draws nothing from goals (§7). |

That last row answers a question the brief raises, and the answer sits outside this contract. `ADR-0065` states the product rule: *"No recommendation may exist without a deadline and a time budget."* So with no goal, the snapshot still exists and `rank()` still may not run — the precondition is on `constraints`, not on `snapshot`. Keeping that separation is what lets Aaroh show a student their practice history before they have set a goal.

**Emptiness is never an error, and never invented away.** `standards/decision_engine.md` requires that *"missing data demonstrably lowers confidence"*, and `context/state.md` records the cold-start requirement: *"A new user with no resume and no DSA history must still get a useful first session."* A snapshot that refused to exist for a new student would make that requirement unimplementable. A snapshot that substituted defaults would make it dishonest. So it reports zero, truthfully, and the engine is obliged to let confidence fall.

---

## 10. Privacy, ownership and classification

**Class: Medium** throughout (`standards/privacy.md`: *"DSA history, readiness scores, recommendation traces"*). Uniformly — §4.3 excludes the free-text fields that would raise it.

**Ownership.** A snapshot is built inside `request_transaction` under the caller's identity (`ADR-0061` I-12), so RLS decides which rows the aggregation sees. The builder issues **no `WHERE user_id = ...` clause**, matching the reasoning already recorded in `backend/app/db/dsa.py`: a second filter is a weaker authorization path that can drift from the policy.

`subject` is carried for trace attribution and equality, and is a `sub` claim already held by the request. It is not a re-identification vector beyond what the request itself carries — but the same rule as `ADR-0066` applies: it must not be echoed in an API response merely because the structure holds it.

**Retention** follows the underlying rows. A snapshot has no independent lifetime; a snapshot inside a trace is retained with that trace, and trace retention is an open decision (`ADR-0061` §9 deletion state machine) — flagged in §13, not settled here.

---

## 11. Determinism, testability and versioning

Determinism is a **correctness** property here, not a nicety: `ADR-0060`'s replay guarantee is void without it.

| Property | How it is obtained |
|----------|--------------------|
| Same rows + same `as_of` ⇒ identical snapshot | Fixed ordering, integer-only arithmetic, no clock (§6) |
| Constructible with no database | `StudentSnapshot` is plain frozen data; a unit test builds one literally |
| Comparable | Frozen and hashable, so equality is structural — a replay test is `==`, not a field-by-field walk |
| Serialisable losslessly | Required by `ADR-0060`'s trace; integers, strings, UUIDs and timestamps only |

**Two construction paths, deliberately.** `from_activities(rows, as_of)` is pure and takes plain data; the SQL aggregation is a separate function in `db/`. Ranking tests then need no database, and the aggregation can be tested against the pure version for agreement. This is the split `ADR-0059` requires — *"the engine is unit-testable with no database"* — made concrete one layer earlier.

**Versioning.** `vocabulary_version` covers the topic list (§4.1). The snapshot **structure** itself is versioned by `engine_version` in the trace: the engine and the shape it consumes change together, and a second version number that can only ever move in lockstep is a liability. If the two ever need to diverge, that is a superseding ADR, not a field added quietly.

---

## 12. Explicit non-goals

This ADR defines a contract and builds nothing. Not in this slice, and not implied by it:

- **No implementation.** No `StudentSnapshot` class, no aggregation query, no endpoint, no migration, no table.
- **No decision engine, ranking, scoring, or candidate generation.** No placeholder `rank()` — `ADR-0060` would demand golden files pinning weights that have no evidence, and `ADR-0065` already rejected an engine skeleton on exactly these grounds.
- **No readiness score**, no ROI calculation, no confidence model.
- **No task catalog** and no catalog schema.
- **No recommendation API**, Daily Mission, notification, or UI.
- **No AI, no provider, no explanation generation.**
- **No solved-problem set.** Deferred with a reason: it needs a catalog identity scheme that does not exist (§4.3). Adding it later is additive and breaks nothing.
- **No resume contribution.** Four decisions block it (`ADR-0065` Option B); when they land, it is a new sibling of `dsa` inside `StudentSnapshot`, not a reshaping of it.
- **`ADR-0059` is not amended here.** §"Unresolved" records a documentation drift for the owner to settle; this ADR does not edit another ADR's decision.

---

## 13. Unresolved and carried forward

| # | Concern | Why it is not settled here |
|---|---------|---------------------------|
| U1 | **`rank()` arity is stated two ways.** `ADR-0059` §"Conceptual contract" says three arguments; `ADR-0060` §Consequences says *"the engine gains an explicit `weights` input parameter"*, and `standards/decision_engine.md` §49 says four. | `ADR-0060` is the later authority on weights and is explicit, so the **four-argument form is authoritative** and this ADR is written against it. But `ADR-0059`'s text was never updated in place. This is documentation drift, not an open decision — and correcting another ADR's text is the owner's call, not a side effect of this one. **Recommend:** a one-line amendment to `ADR-0059` pointing at `ADR-0060`. |
| U2 | Trace retention and deletion for stored snapshots | `ADR-0061` §9's deletion state machine is unbuilt; snapshots inherit whatever it decides. |
| U3 | Whether a solved-problem set enters the snapshot | Blocked on the catalog identity scheme (§4.3). |
| U4 | Resume and interview-practice contributions | Blocked on the resume decisions (`ADR-0065` Option B). |
| U5 | Whether confidence is computed from the snapshot or alongside it | A model question; belongs with the score, not the input contract. |
| U6 | `context/state.md` is stale — it reports `v0.3.0-rls-harness` and *"slice 2 not started"* while `main` is at `v0.7.0-dsa-activity` | Housekeeping, deliberately not bundled into a decision PR. |

---

## Consequences

- The engine can now be specified and unit-tested against a fixed input shape, with no database and no catalog.
- The snapshot/constraints boundary is written down rather than inferred from three prose descriptions, and it is drawn where the privacy classes already fall.
- **`ADR-0066`'s deferral is discharged.** The activity log's stated purpose — *"an input source for the future snapshot"* — now names its consumer.
- Cost: the snapshot is currently one-dimensional. It reports DSA practice and nothing else, and that is an honest reflection of what Aaroh stores, not a gap in this design.
- Cost: denseness restates the vocabulary in every snapshot and every stored trace. Accepted for a total function and an engine that needs no vocabulary.
- Adding a source later is **additive** — a new field beside `dsa` — because nothing in this structure assumes DSA is the only dimension.

## Verification Approach

This ADR is verified by review, not by tests, because it ships no code. When implementation is approved, these are the properties that must be proven:

- Two snapshots built from identical rows and identical `as_of` compare equal, across processes.
- A snapshot is constructible from plain data with no database connection.
- A student with zero activity yields a valid snapshot with sixteen zeroed topics.
- The aggregation returns identical results to the pure constructor over the same rows.
- The aggregation does not truncate: a student with more than 100 activities is counted in full.
- Cross-user isolation holds — a snapshot built for A reflects only A's rows, proven in both directions.
- No snapshot field carries a ratio, score, weight or ranking.
- No float appears in any snapshot field.
