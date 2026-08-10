---
id: ART-ADR-0057
title: "License and Source Availability"
version: 1.0
status: accepted
owner: Rexy-5097
created: 2026-08-10
modified: 2026-08-10
related_adr: None
related_standard: standards/documentation.md
related_checklist: QG-002
related_workflow: master.md
related_agent: chief-architect
---

# Architecture Decision Record: ADR-0057

> **Status:** Accepted | **Date:** 2026-08-10 | **Decider:** Rexy-5097

## Context

The Aaroh repository is public on GitHub and contains no `LICENSE` file. Aaroh is intended to become a commercial product.

Under the Berne Convention and Indian and US copyright law, a work is copyrighted on creation. Publishing source code without a licence grants **no** rights to copy, modify, or distribute it. GitHub's Terms of Service add one narrow exception: publishing in a public repository grants other GitHub users the right to *view and fork within GitHub*. It grants no right to use the code outside GitHub, and no commercial rights.

Absence of a licence is therefore not a gap — it is the most restrictive legally coherent state. The risk to guard against is the opposite one: adding a permissive open-source licence out of convention would irrevocably grant commercial reuse of the entire codebase.

Two secondary pressures pointed the other way and were rejected:

1. **The AgentOS validator** reports `Structural: Missing core root file 'LICENSE'` and `.agentos/manifest.yml` lists `LICENSE` as `MIT License / status: complete`. Both are inherited from the AgentOS template, which is itself MIT-licensed. They describe the *framework's* release requirements, not Aaroh's.
2. **Contribution friction.** Without a licence, outside contributions have no clear IP path.

## Problem Statement

How should Aaroh's licensing state be recorded so that it (a) reserves all commercial rights, (b) is explicit rather than accidental, and (c) does not get "fixed" later by someone reading a validator warning as a defect?

## Alternatives Considered

- **Option A — Permissive OSS (MIT / Apache-2.0).** Rejected. Grants anyone the right to commercialise a verbatim copy of Aaroh. Irrevocable for released versions. Directly contradicts the commercial intent.
- **Option B — Copyleft (AGPL-3.0).** Rejected for now. Closes the network-service loophole and is a legitimate commercial-open-source posture, but it still grants broad use rights, imposes obligations on Aaroh's own future distribution, and complicates any later relicensing or acquisition. It is a decision that deserves legal advice, not a default.
- **Option C — Source-available licence (BUSL-1.1, Elastic, PolyForm).** Rejected for now. Closer to the intent, but each carries specific mechanics (BUSL's change date, PolyForm's variant choice) that should be chosen deliberately with legal input.
- **Option D — No licence; state "all rights reserved" explicitly.** **Accepted.** Preserves every option including A, B, and C. Costs nothing to reverse. Matches the actual legal default rather than fighting it.
- **Option E — Make the repository private.** Rejected. The public repository has standing value for credibility and dogfooding distribution, and being public does not by itself grant rights.

## Decision Rationale

Option D. The repository stays public and **unlicensed**, which under copyright law means **all rights reserved**. No `LICENSE` file is added.

The validator's `LICENSE` warning is reclassified as a **framework-release requirement, not an Aaroh defect**. AgentOS demands a `LICENSE` because AgentOS is distributed as a reusable MIT template. Aaroh is not distributing a template. The warning is expected and must not be resolved by inventing a licence.

This is consistent with `DEVELOPMENT_SETUP.md` §5, which already documents `Structural: 70/100` as expected because "LICENSE is absent by decision."

Contributor implications, to be reflected in `CONTRIBUTING.md` when external contribution actually becomes possible:

- Aaroh accepts no external code contributions until a licence and a CLA/DCO path exist.
- Issues, bug reports, and discussion remain welcome — they carry no copyright entanglement.
- Anyone forking via GitHub's UI acquires only GitHub-ToS fork rights, not usage rights.

## Consequences

- Aaroh retains full commercial freedom; every licensing option remains open.
- The validator will continue to warn about the missing `LICENSE`. **This is expected. Do not resolve it by adding a licence.** Any future change to Aaroh's licence requires a superseding ADR.
- External contributions cannot be merged until a licence decision is made. Accepted cost at this stage — the project is a solo build.
- A licence decision becomes genuinely blocking before: accepting outside contributions, any B2B/institutional agreement, or fundraising diligence.

## Verification Approach

- `LICENSE` is absent from the repository root.
- The `Structural: Missing core root file 'LICENSE'` validator warning is present and is documented as expected in `DEVELOPMENT_SETUP.md`.
- No file in the repository asserts an open-source grant.
