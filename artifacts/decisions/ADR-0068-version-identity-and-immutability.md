---
id: ART-ADR-0068
title: "Version Identity and Immutability"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-12
modified: 2026-08-12
related_adr: ADR-0060
related_standard: standards/decision_engine.md
related_checklist: QG-009
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0068

> **Status:** Accepted | **Date:** 2026-08-12 | **Decider:** Rexy-5097

## 1. Problem

`ADR-0060` requires every recommendation to carry an `engine_version` and a `weights_version`, and requires that *"a stored trace can be replayed at its pinned versions to reproduce the original ranking exactly."* `QG-009` makes trace completeness a **mandatory** gate.

Nothing anywhere says **what one of those identifiers is**. No format, no rule about whether the thing an identifier names can change afterwards. `vocabulary_version` was left unimplemented in `StudentSnapshot` for precisely this reason (`ADR-0067` §4).

Two questions, and only two, are settled here:

- **V1 — What identifies a version?**
- **V2 — Can an identifier ever denote different content?**

## 2. Existing constraints

Everything below is quoted or directly derived from an accepted decision. Nothing is assumed.

| # | Constraint | Source |
|---|---|---|
| R1 | A stored trace must replay *exactly* at its recorded versions | `ADR-0060` §Verification |
| R2 | Weight changes are **reviewable product decisions with visible blast radius**; golden diffs are read *as content* | `ADR-0060` §Golden-file tests |
| R3 | Reproduction must not depend on mutable state — the stated reason DB-editable weights were rejected | `ADR-0060` Option B |
| R4 | Identical input yields **byte-identical** output across processes | `QG-009`, `standards/decision_engine.md` |
| R5 | Engine and weights version **independently** | `standards/decision_engine.md` |
| R6 | A weight set carries provenance: who, when, on what basis, what would revise it | `ADR-0060` §Every weight is a hypothesis |
| R7 | A user-visible score movement is surfaced as a *model update*, discussed in a UI | `ADR-0060` §Score stability |

And one precedent, cited with its limits:

> `templates/experiment_log.md` — **Dataset Provenance → "Version/Hash: [SHA-256 hash of dataset]"**

That is the only place in the repository that states content identity for a data artifact, and it pairs a **version** with a **SHA-256**. It is vendored AgentOS and describes experiment datasets, not weights, so it is a **house convention, not a binding requirement** — but it means choosing SHA-256 here follows the framework Aaroh adopted rather than inventing a primitive.

## 3. Scope

**In:** what identifies a versioned engine artifact, and whether that identifier may ever be reused or re-pointed.

**Out, and untouched:** catalogue identity · lifecycle and retirement · per-user pinning · version coexistence · trace retention · score-model versioning · the engine, ranking, weights values, or any runtime mechanism.

## 4. Decision

> **A versioned Aaroh artifact is identified by an immutable human-readable label. A SHA-256 digest of the artifact's exact bytes accompanies that label as an integrity check. A label, once recorded in any trace, denotes those bytes forever.**

Written as a trace would carry it:

```
weights_version   = <label>
weights_digest    = sha256:<64 hex chars>
```

### 4.1 The label is the identity. The digest is not.

This distinction is load-bearing and is *chosen*, not defaulted into.

The **label** is authoritative identity: it is what a trace references, what a person names in review, what a future pin would point at, and what appears in a changelog. R2 and R7 require an identity a human can read, order, and discuss — *"the model update that moved your score"* is a sentence about a label, never about a hash.

The **digest** is not identity. It answers one question: *are these the bytes that identifier has always meant?* Making it identity would satisfy R1 and R3 while failing R2 and R7 outright, and would drag in a canonicalisation problem the repository has not solved (§7).

### 4.2 What the digest covers

**The artifact file's exact bytes, as committed.** Not a normalised form, not a parsed structure, not a subset of fields.

This is deliberate and it is what makes the decision possible today: hashing raw bytes requires **no canonicalisation decision at all** (§7). It also means the digest covers provenance headers (R6) as readily as coefficients — a change to *"on what basis"* is a change to the artifact, and R6 exists precisely because that text is load-bearing.

## 5. Immutability (V2)

Seven answers, all following from R1 and R3:

1. **Can a label ever point to different content?** **No.** R1 requires exact replay; a re-pointed label makes the replay produce a different ranking with nothing to indicate it. That is the silent failure R3 rejected DB-editable weights to avoid.
2. **Can a label be reused after the artifact it named is retired?** **No.** Traces outlive artifacts, and a trace holds only the label. Reuse would make an old trace resolve to unrelated content. *(When retirement itself happens is `V4`, out of scope — this rule is stated now so `V4` cannot quietly permit reuse later.)*
3. **Can a versioned file be edited in place?** **No.** A change produces a new label.
4. **Must a content change change the identifier?** **Yes** — any content change, without exception.
5. **Does a metadata- or provenance-only change require a new version?** **Yes.** The digest covers the whole file, and R6 makes provenance part of what a weight set *is*.
6. **Does reformatting change the digest?** **Yes** — the bytes changed, so a new label is required. **This is a real cost**, named plainly in §9 rather than engineered around.
7. **Is immutability enforced technically or by rule?** **By rule, now.** This slice ships no runtime mechanism. §8 records what enforcement would later look like, as a consequence rather than a commitment.

## 6. Failure cases

| # | Case | Result | Why |
|---|---|---|---|
| 1 | A versioned file is edited without changing its label | **DETECTED** | Recomputed digest ≠ the digest in the trace. Not *prevented* — no runtime check exists yet (§5.7). |
| 2 | A second artifact is created reusing an existing label | **DETECTED** | Same as 1. Forbidden by §5.2. |
| 3 | Two artifacts accidentally share a human label | **DETECTED** | Their digests differ, so the collision surfaces instead of silently resolving. |
| 4 | The artifact is copied to another machine | **ALLOWED** | A byte copy has the same digest. See the `.gitattributes` risk in §9. |
| 5 | A trace records label **and** digest | **ALLOWED** | The intended state — this is what makes 1–3 detectable at all. |
| 6 | Label stable, content changed | **DETECTED**, and a rule violation | Identical to 1. |
| 7 | Digest changed, label unchanged | **DETECTED** | The same event as 6, observed from the other side. |
| 8 | Two different labels, byte-identical content | **ALLOWED** | Equal digests, distinct labels. Redundant but harmless: the label is identity (§4.1), so two names for the same bytes are two legitimate versions. |

Cases 1, 2, 3, 6 and 7 are **DETECTED, not PREVENTED**. Under a documented-rule regime that is the honest ceiling, and saying "prevented" would overclaim.

## 7. Canonicalisation — why it is not a blocker

Digesting a YAML file *by meaning* would demand decisions the repository has never made: key ordering, whitespace, comment retention, line endings, encoding.

**None of that is required here.** The digest covers the file's exact bytes (§4.2), and byte identity is already fully defined — it needs no algorithm and admits no ambiguity.

Canonicalisation becomes necessary only under a requirement nobody has stated: *"two textually different but semantically equal files must share a digest."* If that requirement ever appears, it is a **follow-up decision**, and §5.6 is the visible cost of not having it today.

## 8. What this does not decide

> **This decision does not resolve catalogue identity, lifecycle, per-user pinning, trace retention, or score-model versioning.**

Additionally, and importantly:

**The label format is NOT decided here.** The repository contains three unrelated conventions — ADR frontmatter `1.0`/`1.1`/`1.2`, git tags `v0.9.0-snapshot-builder`, and the illustrative `weights/v1.yaml` — and **none governs engine artifacts**. `standards/documentation.md` mentions semantic versioning only for *changelogs*, at "Production Grade".

*Label + digest does not mean semver + digest.* The identity **model** is settled; the **lexical format** is deferred to whichever slice authors the first real artifact (`E4`, weights). Nothing in §4 or §5 depends on the format: immutability and integrity hold for any label that is a stable string.

No runtime mechanism is built: no registry, no resolver, no storage, no verification code, no migration.

## 9. Consequences

- `vocabulary_version` (`ADR-0067` §4) becomes implementable once a label format exists — the blocking question was identity semantics, and that is now answered.
- Traces gain a second field per versioned artifact. Cheap, and it is what makes §6 detectable.
- **Reformatting a weights file is a version bump** (§5.6). Accepted deliberately: the alternative is a canonicalisation algorithm invented ahead of any requirement for one.
- Byte-exact digests are sensitive to line-ending translation. If artifacts are ever digested from a working tree rather than from committed content, `.gitattributes` must pin them; flagged as an implementation risk, not decided here.
- Immutability is a rule with no enforcement until something checks it. That gap is recorded, not hidden.

## 10. Alternatives considered

**Option A — human-readable label only.** *Rejected.* It satisfies R2 and R7 but not R1: a label alone cannot tell that the file behind it changed, so a replay would silently produce a different ranking. That is exactly the class of silent mutability R3 rejected DB-editable weights to avoid, and detecting it is the whole point of the trace.

**Option B — content digest only.** *Rejected*, though it satisfies R1, R3 and R4 perfectly. It fails R2 and R7: a bare hash cannot be ordered, discussed, or shown to a student as *"a model update"*, and golden-file review is human review. It would also force the canonicalisation decision of §7 to be made now, ahead of any requirement.

**Option C — immutable label + byte digest.** **Accepted.** The only option satisfying R1, R2, R3, R4 and R7 together, and the only one that defers canonicalisation honestly rather than by omission. It matches the `Version/Hash` pairing the framework already uses for dataset provenance.

**Option D — git commit SHA as the identifier.** *Rejected.* Attractive because it is free and immutable, but it identifies a *repository state*, not an artifact: it changes when unrelated files change, violating R5 (engine and weights version independently), and one commit touching both would give them the same identifier.

## 11. Verification

Review-only; this ADR ships no code.

- No versioned artifact exists yet, so nothing is asserted about one.
- When the first artifact is authored, its slice must show: a label, a digest of committed bytes, and a test that a changed file changes the digest.
- `QG-009` trace completeness continues to require `engine_version` and `weights_version`; this ADR adds the digest as their companion, not a replacement.
