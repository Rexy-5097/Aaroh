---
id: ART-ADR-0069
title: "DSA Catalogue Contract (V1)"
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

# Architecture Decision Record: ADR-0069

> **Status:** Accepted | **Date:** 2026-08-12 | **Decider:** Rexy-5097

## 1. Scope

`ADR-0059` names `catalog` as an engine input. Three ADRs then described it only as *"the candidate tasks"*. The E3 investigation found no task taxonomy, no identity scheme, no item specification and no example anywhere in the repository — the contract was blocked on a product question, not an architectural one.

**That question is now answered.**

> **PRODUCT DECISION (approved 2026-08-12): Aaroh V1 recommendation candidates are DSA problems / practice tasks only.**
>
> Multi-domain recommendation — resume, interview, career-search, project work — is explicitly deferred. No generic task abstraction is designed here.

Every decision below carries its basis:

| Tag | Meaning |
|---|---|
| **[E]** | Decided by existing repository evidence |
| **[P]** | Decided by the approved product decision above |
| **[R]** | **Recommendation requiring approval** — not yet decided |
| **[U]** | Undecided, and deferred with a named owner |

Nothing marked **[R]** may be treated as settled.

## 2. What a catalogue item represents

**[P][E]** One catalogue item is **one DSA practice problem that Aaroh can recommend a student work on next.**

It is a *thing to do*, authored by Aaroh, and it is deliberately not the same object as a `dsa_activities` row, which is a *thing a student did*. `ADR-0066` records history; this records opportunity. The two meet only through the topic vocabulary (§6) and, eventually, through problem matching (§9).

**[E]** `README.md` bounds this from the other side: *"Aaroh is not a course catalogue or a job board."* A catalogue item is not courseware, not a lesson, and not a job.

## 3. Identity

**[R] An immutable, human-readable kebab-case slug is the identity of a catalogue item.**

`ADR-0068` already settled the discipline — an immutable human-readable label identifies an artifact, never reused, never re-pointed — and its reasoning transfers directly: identity must be reviewable, because a hand-authored catalogue is reviewed in pull requests and appears in `ADR-0060`'s golden files. `two-sum` in a golden diff is readable; a UUID is noise, and a golden file full of noise is a golden file nobody reads.

| Option | Assessment |
|---|---|
| **Immutable slug** | **Recommended.** Reviewable, stable, diff-friendly, platform-independent. Cost: authors must resist renaming — a mistake means a new item, never an edit (`ADR-0068` §5). |
| UUID | Rejected. Stable and collision-free, but unreadable in golden files, PR reviews and traces — the same objection `ADR-0068` raised against digest-only identity. |
| Platform + external problem id | Rejected **as identity**. It binds Aaroh's identity to a third party, breaks when a problem exists on two platforms or none, and `ADR-0066` already established the opposite direction: `problem_ref` is *"the PLATFORM-INDEPENDENT identity of the underlying problem, and the key a future ingestion layer maps platform ids onto."* Platform ids are references (§8), not identity. |
| Slug + digest | Rejected as unnecessary *per item*. `ADR-0068`'s digest protects an **artifact**; the catalogue artifact is digested as a whole (§9), which already covers every item in it. |

**[E]** Identity is **not** `ADR-0066`'s `problem_ref`. That value is derived from free text a student typed and is deliberately weak — lowercase and whitespace collapse only. It is a matching key, not a primary key, and §9 keeps that distinction.

## 4. Required fields

**[R]** The smallest item that is rankable at all:

```
slug          identity (§3)
title         display; the problem's name as Aaroh states it
topics        one or more entries from app.domain.dsa.TOPICS (§6)
difficulty    one of easy | medium | hard (§7)
```

Four fields. Each earns its place: `slug` identifies, `title` is the only thing a student can be shown, `topics` is the sole join to the snapshot (`ADR-0067` §8), and `difficulty` is the only other dimension the snapshot carries.

**No other field is required.** `ADR-0066`'s standard applies — *"no speculative fields: unused personal data is a liability"* — and while catalogue data is not personal, unused fields still have to be authored, reviewed and kept true.

## 5. Optional fields

**[R]** `external_refs` — zero or more platform references (§8). Nothing else.

**Deliberately absent:** description, prerequisites, tags beyond topics, editorial notes, author, popularity, acceptance rate, company associations. Each was considered and refused: none is required to rank, and every one is a maintenance obligation on hand-authored data.

## 6. Topic semantics

**[E]** `ADR-0067` §8 is binding: *"when the catalog is designed, its topic tags must be drawn from the same `TOPICS` tuple. A catalog with its own list would make the join lossy in a way no test would catch until recommendations quietly stopped covering some topics."*

Resolving the four open questions:

| Question | Decision | Basis |
|---|---|---|
| One topic or several? | **Several permitted; at least one required.** | **[R]** A real problem is often two-pointers *and* arrays. Forcing one would make the author discard a true tag, and the snapshot is dense over all sixteen topics so multiple matches cost nothing. |
| Required or optional? | **Required, minimum one.** | **[E]** Topics are the only join to the snapshot. An untagged item can never be matched to a student's state, so it is unrankable — the catalogue must not contain items the engine cannot reason about. |
| Does order matter? | **No. Ordering is not significant** and must not be relied on. | **[R]** Treating position as primacy would smuggle a weight into the catalogue. Authors should write them in vocabulary order for reviewable diffs; the engine must treat the set as unordered. |
| May a task be untagged? | **No.** | Follows from the above. |

**[E]** No second vocabulary is created. `TOPICS` remains defined once, in `app/domain/dsa.py`.

## 7. Difficulty semantics

**[R]** The catalogue reuses the same three values — `easy`, `medium`, `hard` — **and the meaning is not the same**, which must be stated rather than glossed.

- **Snapshot difficulty** is the student's *perception*. `ADR-0066`: *"Aaroh's own scale, not a platform's. A `medium` the student found hard is a genuine signal, and importing a platform's calibration would erase it."*
- **Catalogue difficulty** is the *authored intrinsic level* of the problem.

They share a vocabulary so they can be compared — the snapshot's per-`(topic, difficulty)` counts are only meaningful against a task difficulty on the same scale. But they can legitimately **disagree**, and that disagreement is signal, not error: a student whose `easy` attempts outnumber solves is telling Aaroh something. **How** the engine uses that disagreement is a scoring question, deferred to the score-model slice.

**[R]** A second difficulty vocabulary is **not** created. Doing so would require a mapping between them, and any mapping is a modelling coefficient — which `ADR-0060` places in weight files, not in data.

## 8. External references

**[E]** `ADR-0066` deferred platform ingestion; `context/state.md` records that *LeetCode has no official public API*. Nothing here changes that.

**[R]** The catalogue **may** carry external references as optional, non-identity metadata: a platform name and that platform's problem identifier or URL.

Three things are kept strictly separate:

| Layer | Status |
|---|---|
| **Catalogue identity** (§3) | Decided — Aaroh's own slug, independent of any platform |
| **External identity** | Optional reference data, never identity, never required |
| **Ingestion** | **Not built and not designed.** No HTTP client, no scraping, no platform API, no terms accepted. |

A reference is a string Aaroh authors by hand. Recording *"this problem is `two-sum` on some platform"* creates no dependency; **calling** that platform does, and nothing here calls anything.

## 9. Versioning, immutability and the trace

**[R] The catalogue is a versioned artifact, and `ADR-0068` applies to it in full.** An immutable human-readable label identifies a catalogue version; a SHA-256 digest of its exact bytes accompanies it; labels are never reused and content is never edited in place.

**[R] The catalogue should be a versioned file loaded by the caller and passed into the engine — not a database table.** This is the load-bearing structural recommendation of this ADR, and it follows the shape `ADR-0060` already chose for weights:

- It preserves engine purity by construction: the engine performs no I/O, exactly as with weights.
- It is immutable and reviewable — a catalogue change is a diff in a pull request, which is what makes `ADR-0060`'s *"visible blast radius"* true for the catalogue too.
- **It avoids introducing a non-user-owned table entirely**, which is a security decision Aaroh does not otherwise have to make (§12).
- A hand-authored V1 catalogue has no runtime writer, so a table would buy mutability nobody asked for.

**[E] A catalogue version must appear in the decision trace.** `ADR-0060`'s trace table lists `engine_version` and `weights_version` but **no catalogue version** — and replay requires one: the same snapshot, constraints and weights against a different catalogue produces a different ranking, so a trace without it cannot satisfy *"a stored trace can be replayed at its pinned versions to reproduce the original ranking exactly."*

This is an **addition** to that table, not a contradiction of it. `ADR-0060` is not amended here; the trace slice (`E6`) must carry `catalogue_version`, and this ADR records why.

**[U]** Catalogue lifecycle — retiring an item, whether versions coexist, whether a retired slug's history remains resolvable — is **not decided here**. It belongs with `V4` lifecycle, still open from the E1 investigation.

## 10. Time semantics

**[R] The catalogue carries NO time estimate.** This is the decision most likely to be contested, so the reasoning is given in full.

The ranking objective is *readiness gain per unit of available time* (`context/architecture.md`), so the engine unquestionably needs a time cost. The question is **where it comes from**, and there are only two honest answers:

**Rejected — a per-item `estimated_minutes` authored into the catalogue.** There is no ground truth for it. How long a DSA problem takes is a property of the *student*, not the problem, and with no ingestion and no outcome data the number would be invented by whoever writes the catalogue entry. `ADR-0066` faced exactly this and refused: `minutes_spent` is optional because *"forcing a number would produce invented ones, which is worse than a null the engine can treat as unknown."* Inventing minutes for a problem the author has never watched anyone solve is weaker still.

**Recommended — time cost is a function of difficulty, owned by weights.** A per-difficulty duration is precisely what `ADR-0060` calls a hypothesis: *"Every weight is a hypothesis until usage data validates it"*, and *"No numeric ranking coefficient appears in decision-engine source; all live in versioned weight files."* Placing it in weights makes it versioned, reviewable, pinned in traces and revisable the moment `minutes_spent` data accumulates — which is exactly the evidence that would correct it. Placing it in the catalogue freezes a guess into data and makes revising it a bulk edit of every item.

**[U] The numbers themselves are not decided here** — no minutes per difficulty, no ranges, no units beyond "minutes", no integer-versus-float rule. That is the **score-model slice's** decision, and it inherits one constraint from `ADR-0059`: output must be byte-identical across processes, which floating-point arithmetic makes harder to guarantee.

**[R]** If per-item timing is ever genuinely needed, it is added later as an **optional override** on the item. Additive, and it breaks nothing.

## 11. Candidate generation and eligibility

**[E]** `standards/decision_engine.md`: *"Keep candidate generation separate from ranking. Two pure steps are easier to test than one."* The same standard's Scope governs *"candidate generation"*, placing it inside the engine's world rather than the caller's.

**[R]** The boundary:

```
catalogue artifact  →  candidate selection (pure)  →  ranking (pure)  →  result
```

Both steps are pure functions in the engine package. Selection decides *eligibility* — which items may be considered at all; ranking decides *order*. **The catalogue itself performs no selection and no ranking**: it is inert data, and an item carries no field expressing preference, priority or suitability.

**[U] Which function receives which argument is genuinely open**, because `ADR-0059`'s signature names the parameter `catalog`, not `candidates`. Whether `rank()` takes the full catalogue and selects internally, or takes a pre-selected set, is an **`E2` decision** — it changes the engine signature — and is deferred there rather than settled by a catalogue ADR.

**[U]** Eligibility *rules* — whether solved problems are excluded, whether difficulty is gated by history — are scoring decisions, deferred to the score-model slice. Note that excluding already-solved problems additionally depends on `ADR-0067` U3, which is itself blocked on matching `problem_ref` to catalogue items (§3).

## 12. Security and the RLS structural boundary

**[E]** `backend/tests/test_rls_structural.py` states the requirement precisely:

> *"If a genuinely non-user-owned table is ever needed — a task catalogue, engine weight metadata — these tests will fail loudly until the exemption is designed deliberately: an explicit allow-list keyed to an ADR, with the exempted table still asserted for the properties that do apply to it (RLS enabled, anon denied). That is a security decision requiring its own governance record, not a blank cheque written in advance."*

**[R] The recommendation in §9 — catalogue as a versioned file — means this exemption is never needed.** No table, no allow-list, no migration, no weakening of a structural test that currently asserts every table in `public` with no exemptions. That is the strongest available answer, and it is a genuine reason to prefer the file.

**[R] If a catalogue table is chosen instead**, the smallest compliant design is recorded here so the choice is informed rather than discovered later:

1. An explicit allow-list mapping the table name to **this ADR number** — never a bare set, and never empty-by-default. `context/state.md` records that `NON_USER_OWNED_TABLES` was **removed** in slice 1 because *"a blank security exemption is worse than a future addition failing loudly"*; any reintroduction must be keyed to a decision, which is precisely what the test demands.
2. The exempted table remains asserted for every property that still applies: **RLS enabled and forced**, `anon` revoked, and **no write grant to `authenticated`** — students read the catalogue, never write it.
3. Only the ownership assertions (a `user_id` column, owner-scoped policies) are skipped, because they are meaningless for data owned by nobody.
4. A governance regression test proving the allow-list cannot silently grow — the same both-directions discipline every other check carries.

**Nothing in §12 is implemented here.** No test is modified, no allow-list is added, no table is created.

## 13. Boundaries

**[E]** Derived from `ADR-0067` §7–8, `ADR-0065`, `ADR-0060` and `standards/decision_engine.md`:

| Information | Catalogue | Snapshot | Constraints | Weights | Engine |
|---|:---:|:---:|:---:|:---:|:---:|
| task identity, title | ● | | | | |
| task topics, difficulty | ● | | | | |
| time cost per difficulty | | | | ● | |
| practice history, counts, recency | | ● | | | |
| deadline, weekly hours, target role | | | ● | | |
| decision instant (`as_of`) | | ● | | | |
| eligibility rules | | | | ● | ○ |
| score, rank, ordering | | | | | ● |
| explanation prose | | | | | |

● owns it · ○ applies it. Explanation prose belongs to none of them — `ADR-0059` places it downstream, template-first, after the engine has decided.

**The catalogue describes problems. The snapshot describes a student. Neither may contain the other**, and no catalogue item may carry a student identifier, a score, a weight or a rank.

## 14. Cold start

**[E]** `context/state.md`: *"A new user with no resume and no DSA history must still get a useful first session."*

**[R]** This imposes **no additional fields**. It imposes two obligations elsewhere:

1. **Totality** — every item must be rankable against an all-zero snapshot. `ADR-0067` §9 already guarantees such a snapshot exists and is dense over all sixteen topics, so no item may require prior history to be scored. The four required fields (§4) all satisfy this: none derives from student data.
2. **Coverage** — a *content* requirement, not a schema one: the catalogue must actually contain `easy` items across a reasonable spread of topics, or a beginner's ranking is drawn from an empty or lopsided pool. This is an authoring obligation on whoever populates V1, and it is testable once content exists.

The cold-start **algorithm** is not designed here.

## 15. Privacy

**[E]** The catalogue contains **no student data of any kind** — no `user_id`, no target role or company, no practice history, no notes, no derived user features. It is authored content about publicly-known problems and falls outside `standards/privacy.md`'s subject data classification entirely.

**[R]** External references (§8) carry no privacy consequence while ingestion stays unbuilt: a stored URL is a string Aaroh wrote, and no student data leaves the boundary because nothing is called. That changes the moment ingestion is designed, which is why §8 keeps the three layers separate.

## 16. Determinism

**[E]** `ADR-0059` requires byte-identical output across processes. Consequences for the catalogue:

- **Item ordering within the artifact must not affect the result.** The engine must not depend on file order; ties are broken by an explicit rule, which is `E6`'s decision and does not exist yet.
- **Topics are an unordered set** (§6), so two authorings differing only in tag order must produce identical rankings.
- **Slugs are stable and unique** within a catalogue version — the precondition for any deterministic tie-break keyed to identity.

## 17. Explicit non-goals

Not built, not designed, not implied: the catalogue itself (no file, no table, no data, no migration) · any catalogue item · ranking, scoring, weights or `RankedResult` · candidate-selection or eligibility code · platform ingestion, HTTP clients or scraping · an API route · a UI · AI or explanation generation · any change to `test_rls_structural.py` or the governance checks · **multi-domain tasks of any kind**.

## 18. Deferred decisions

| # | Deferred | Owner |
|---|---|---|
| D1 | Time values per difficulty — minutes, ranges, integer vs float | Score-model slice |
| D2 | Whether `rank()` receives the catalogue or a pre-selected candidate set | **`E2`** — it changes the engine signature |
| D3 | Eligibility rules, including excluding solved problems | Score-model slice; also blocked on `ADR-0067` U3 |
| D4 | Catalogue lifecycle: retirement, coexistence, resolvability of retired slugs | `V4` lifecycle, open from E1 |
| D5 | Tie-breaking between equal scores | `E6` |
| D6 | Adding `catalogue_version` to `ADR-0060`'s trace table | `E6` trace slice |
| D7 | Matching `problem_ref` to catalogue slugs | Whichever slice needs the solved-problem set |
| D8 | Multi-domain recommendation | Explicitly deferred by the approved product decision |
| D9 | Label format for catalogue versions | Still open from `ADR-0068` §8 |

## 19. Consequences

- E3 is unblocked, and E2 loses one of its four dependencies: a ranked entry can now reference a task by slug.
- Choosing the file form (§9) means Aaroh still has **no non-user-owned table**, and the structural RLS suite keeps asserting every table with no exemptions.
- The catalogue becomes a reviewable artifact: adding a problem is a pull request with a visible diff.
- Cost: a hand-authored catalogue must be written and kept true, and coverage (§14) is a standing obligation with no automated check until content exists.
- Cost: time-as-weights (§10) means the first weight set cannot ship without duration coefficients, which raises the stakes on the score-model slice rather than lowering them. That is deliberate — the alternative was inventing the numbers here, where they would be invisible.
