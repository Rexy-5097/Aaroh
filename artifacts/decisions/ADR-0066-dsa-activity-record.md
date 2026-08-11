---
id: ART-ADR-0066
title: "DSA Activity Record (Manual Entry)"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-10
modified: 2026-08-10
related_adr: ADR-0065
related_standard: standards/privacy.md
related_checklist: QG-011
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0066

> **Status:** Accepted | **Date:** 2026-08-10 | **Decider:** Rexy-5097

## Context

`ADR-0065` supplied the engine's `constraints` input. `snapshot` — the student's current readiness state — has no source at all.

DSA practice is the first real component of it. What the repository decides today is thin and worth stating exactly, because everything else in this ADR is new:

| Already decided | Where |
|---|---|
| DSA history is **Medium**-class data | `standards/privacy.md` |
| **Manual entry for V1.** LeetCode has no official public API; Codeforces has one, terms unverified | `context/state.md` |
| Platform ingestion deferred to a later ADR | `ADR-0065` |
| Ownership shape: `user_id`, RLS enabled and forced, policies in the creating migration | `ADR-0061` |
| User-owned rows are removed by FK cascade on account deletion | `ADR-0061` section 9 |

No conflicting decision exists. `ADR-0065` states "no DSA schema" as the scope of *that* slice, not as a prohibition.

**`snapshot` has no defined structure.** `ADR-0059` names the parameter; `ADR-0065` describes it as "the student's current readiness state". Neither defines a field. This ADR does not invent one — see section 8.

## Problem Statement

What is the smallest honest model of a student's DSA practice that can be entered by hand, owned safely under RLS, and later feed a snapshot whose shape nobody has decided yet?

## Alternatives Considered

**Option A — Session-level records** ("I practised graphs for 45 minutes"). Rejected as the unit. It captures time, which the ROI objective needs, but not which problems or how they went, so weak-topic detection — the reason to collect topics at all — becomes guesswork.

**Option B — Aggregate counters per topic** (`arrays: 42 solved`). Rejected. Cheap to store and impossible to correct, re-derive, or explain. It also destroys the audit trail the product's transparency principle depends on: a student asking "why is my graphs score low" would get a number with no history behind it.

**Option C — Problem-level activity records, append-only.** **Accepted.** One row per practice event against one problem. Time is optional per event, so both the topic signal and the time signal survive. Aggregates are derivable; the reverse is not true.

**Option D — Problem-level plus a separate session table now.** Rejected as premature. A session model is a real future need, but building both means designing the join before either has a consumer. Section 8 records how the session model can be added later without reinterpreting these rows.

## Decision

### 1. What a DSA Activity is

**One row records one practice event by one student against one problem at one time.**

- **What makes two activities different:** they are separate events. Two rows may name the same problem, the same topic, the same difficulty and the same outcome and still be distinct — the second is a re-solve, which is signal, not duplication.
- **Identity of an activity:** a surrogate `id` (UUID). Nothing else is unique.
- **Identity of the underlying problem:** `problem_ref` (below). The distinction between "the problem" and "an attempt at the problem" is deliberate and is what makes future ingestion possible.

### 2. Problem identity — platform-independent by construction

Manual entry has no stable identifier. A student types a title; the same problem may be typed `Two Sum`, `two sum`, or `Two  Sum`.

Two fields, doing different jobs:

| Field | Job |
|-------|-----|
| `problem_title` | Exactly what the student typed, trimmed. For display. Never used for grouping. |
| `problem_ref` | A normalised form of the title: lowercased, internal whitespace collapsed, trimmed. Derived, stored, and used for grouping. |

`problem_ref` is **platform-independent**. It is not a LeetCode slug, not a Codeforces id, and carries no platform semantics. A future ingestion layer maps a platform identifier onto a `problem_ref` — it does not replace it, and existing rows do not need reinterpreting.

Normalisation is deliberately weak: lowercase and whitespace only. No stemming, no fuzzy matching, no synonyms. A stronger normaliser would silently merge genuinely different problems, and merging is unrecoverable while splitting is not.

### 3. Outcome — required by the stated grain

An activity is "one attempt/completion/practice record". Those are not the same event, so the record must say which:

```
outcome ∈ { solved, attempted }
```

**"Solved" means the student judges they arrived at a working solution.** It is self-reported and is not verified by Aaroh — there is nothing to verify against under manual entry, and pretending otherwise would be the fabricated rigour this project's principles forbid.

`attempted` means engaged with and not completed. Both are signal: a topic with many attempts and few solves is precisely the weakness the engine should eventually act on.

Two values only. `skipped`, `reviewed`, `revisited` and similar are not added, because no decision requires them.

> This field is an inference from the approved grain rather than an explicitly listed one. Without it, "attempt" and "completion" collapse into an indistinguishable row and the grain as stated cannot be represented.

### 4. Topic vocabulary — Aaroh-controlled, domain-layer

The repository contains **no existing DSA topic vocabulary** (searched exhaustively). This ADR establishes one: 16 broad interview-DSA topics, as lowercase kebab-case slugs.

```
arrays                     stacks-and-queues     binary-search
strings                    linked-lists          sorting
hash-tables                trees                 recursion-and-backtracking
two-pointers               graphs                dynamic-programming
sliding-window             heaps                 greedy
                                                 math-and-bit-manipulation
```

Chosen to be **broad and stable**. A finer taxonomy (`monotonic-stack`, `union-find`) would be more precise and would churn as opinion shifts; these sixteen are the level at which students and interview material actually agree.

**Held in the domain layer, not a PostgreSQL `ENUM`.** Adding a topic must be a code change with a test, not a migration and a type alteration. Unknown topics are rejected by domain validation and by tests.

No AI classification. The student picks the topic.

### 5. Difficulty

```
difficulty ∈ { easy, medium, hard }
```

Domain-controlled, **not** platform-derived. The words are the industry vernacular; Aaroh does not adopt LeetCode's calibration, and a problem's difficulty here is the student's own assessment. That matters: a "medium" a student found hard is a genuine signal, and importing a platform's label would erase it.

Difficulty **also** carries a database `CHECK`, unlike topic. The asymmetry is deliberate: difficulty is a closed three-value set that will not change, so a structural constraint is free defence in depth; the topic list is designed to grow, so a `CHECK` would turn every addition into a migration.

### 6. Time spent

`minutes_spent`, optional, `1..600` when present.

Optional because a student recording practice retrospectively often does not know. Forcing a number would produce invented ones, which is worse than a null the engine can treat as unknown.

The upper bound is 600 minutes (10 hours). Beyond that the record is describing a study session, not one problem — and the session model is explicitly out of scope (section 8).

### 7. Platform — metadata only

`platform`, optional free text, ≤60 characters.

It records where the student practised. It does **not**: affect ownership, affect authentication, determine difficulty semantics, drive validation, or imply any integration. There is no platform allow-list, because constraining it would be a decision about which platforms Aaroh endorses, and no such decision exists.

No platform-specific problem identifier is stored. `problem_ref` (section 2) is the identifier, and it is platform-independent.

### 8. Relationship to the future snapshot

> **DSA activity is an input source for the future snapshot; the snapshot schema remains a separate decision.**

That sentence is the whole of the relationship. This ADR does not define snapshot fields, does not compute aggregates, and does not add derived columns.

What these rows will support once a snapshot is designed: counts by topic, by difficulty and by outcome; solve-versus-attempt ratios as a weakness signal; recency and consistency from `occurred_at`; and time totals where `minutes_spent` is present.

**Why a future session model is not blocked.** A session is a time window containing practice; an activity is a problem-level event within one. A later `dsa_sessions` table can reference these rows by adding a nullable `session_id`, without changing what an existing row means. Rows recorded before sessions exist simply have no session — which is true, not a gap.

### 9. Ownership, RLS, and API

Identical to `ADR-0065`, because the shape is proven:

- `user_id` with `DEFAULT auth.uid()`, cascading from `auth.users`.
- RLS **enabled and forced**; `SELECT` and `INSERT` policies with `USING` / `WITH CHECK`; `anon` revoked.
- **No `UPDATE` or `DELETE` policy, and no such endpoints.** An activity log is append-only: a past practice event is a fact, and editing it would corrupt the history the engine will reason over. With RLS enabled and no policy, both operations are denied by default rather than by a rule someone must remember.

Endpoints, both behind the `ADR-0064` dependency:

- `POST /v1/dsa-activity` — record one activity. Returns the created row.
- `GET /v1/dsa-activity` — list the caller's activities, most recent first, bounded.

The request model declares **no owner field** (`ADR-0065` I-30). Ownership comes from the verified identity.

### 10. Privacy, retention, deletion

**Medium** class per `standards/privacy.md`: ownership-enforced, never shared externally, pseudonymous in analytics. Lower than resume data — it reveals study habits, not identity or employment — but it is still a behavioural record of a named student and is protected by the same RLS boundary.

Retained while the account exists. Removed by **FK cascade** when the `auth.users` row is deleted (`ADR-0061` section 9). **No deletion pipeline is built here**, and none is needed: the cascade is the hook, and it is tested.

### 11. What is deliberately NOT collected

No problem URL · no platform problem id · no submitted code · no runtime or memory statistics · no language · no contest or streak metadata · no tags beyond the single topic · no notes or free-form reflection · no company associations · no verification of any self-reported value.

Each was considered and rejected for the same reason: nothing in the product requires it yet, and unused personal data is a liability under `standards/privacy.md`.

## Security Invariants

No new invariant. `ADR-0065` **I-30** (request models never declare an owner identifier) already covers this slice generally, and duplicating it would add machinery without adding a guarantee.

## Threat Model

| # | Threat | Mitigation | Residual |
|---|--------|-----------|----------|
| D1 | A student reads another's activity | RLS `USING (user_id = auth.uid())`, proven both directions through HTTP | Low |
| D2 | A student records activity owned by another | `WITH CHECK` plus `DEFAULT auth.uid()`, proven by direct SQL naming another owner | Low |
| D3 | The request body chooses the owner | No owner field, `extra="forbid"`, I-30 | Low |
| D4 | Unauthenticated access | `ADR-0064` dependency on both endpoints; asserted to persist nothing | Low |
| D5 | Unbounded reads | `GET` is bounded by a fixed limit | Low |
| D6 | Study habits inferred by a third party | Medium-class, never sent anywhere, never logged | Low |
| D7 | Append-only log corrupted by edits | No `UPDATE`/`DELETE` policy or endpoint | Low |
| D8 | Free-text fields used as an injection vector | Parameterised queries throughout; length-bounded | Low |

## Failure Modes

| Failure | Cause | Detection | Recovery |
|---------|-------|-----------|---------|
| Topic vocabulary drifts from reality | Interview practice changes | Product review | Extend the domain list; no migration required |
| `problem_ref` merges distinct problems | Two problems share a title | Not automatically detectable | Accepted: normalisation is deliberately weak (section 2) |
| A mistyped activity cannot be corrected | Append-only by design | User report | **Known limitation** — see below |
| Activity survives account deletion | FK cascade missing | Deletion test | Restore the cascade |

## Testing Strategy

Minimum coverage, not a target.

**Domain:** every accepted topic · unknown topic rejected · case sensitivity of the vocabulary · each difficulty · unknown difficulty rejected · both outcomes · unknown outcome rejected · `minutes_spent` absent, at bounds, out of bounds, non-integer, and `bool` (an `int` subclass that would otherwise pass as 1 minute) · empty and whitespace `problem_title` · length bounds · `problem_ref` normalisation including case and internal whitespace.

**API and isolation:** create and read back · **A cannot read B's activity** and vice versa · a client-supplied `user_id` is refused · unauthenticated create and read refused and persisting nothing · invalid input persisting nothing · the same problem recorded twice yielding two distinguishable rows that do not overwrite each other · ordering and bounding of the list.

**Direct SQL:** an `INSERT` naming another owner is refused; `UPDATE` and `DELETE` are denied for having no policy — the tests that make `WITH CHECK` and the absent policies load-bearing, since the API cannot exercise them.

**Deletion:** removing the `auth.users` row removes the activity.

**Structural:** the existing catalogue assertions must cover the new table with **no exemption added**.

**Mutation testing is mandatory.** Each of removing RLS, removing `FORCE`, weakening `USING`, weakening `WITH CHECK`, allowing client ownership, removing topic validation, widening difficulty, removing minutes bounds, making duplicates impossible, and bypassing authentication must be caught by a *named* test. A batch harness result that looks surprising is re-run individually before it is believed — a batch misreport already occurred once in this project.

## Governance Requirements

No new check. I-30 covers the owner-field invariant; the existing seventeen cover connections, JWT handling, `service_role`, RLS on new tables, and identity on database-touching handlers. Adding a DSA-specific check would be machinery without an invariant.

## Known Limitations

1. **Activities cannot be edited or deleted by the student.** Append-only is right for a practice log, but a mistyped entry is currently permanent. Correction needs its own decision — soft-delete versus correction record — and neither exists.
2. **Everything is self-reported and unverified.** Under manual entry there is nothing to verify against. Any later claim about a student's DSA ability must carry that caveat.
3. **`problem_ref` can collide** across genuinely different problems sharing a title. Accepted; weak normalisation is the safer failure.
4. **No aggregates, no snapshot, no ranking.** This slice stores facts. It answers *"what has this student recorded?"* and deliberately not *"what should they do next?"*
5. **Platform ingestion remains deferred** to its own ADR; nothing here calls an external service.

## Verification Approach

- Cross-user isolation asserted both directions through HTTP.
- `WITH CHECK` and the absent `UPDATE`/`DELETE` policies proven by direct SQL, since the API cannot reach them.
- Cascade deletion proven by removing the user row.
- Mutation testing proves each property is defended by a specific named test.
- No claim is made that recorded activity is accurate — only that it is the student's own, isolated, and validated in shape.
