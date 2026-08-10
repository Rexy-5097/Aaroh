# Engineering Workflow

> **Layer:** Project | **Status:** Active | **Owner:** Rexy-5097
>
> How work reaches `main` in Aaroh: branches, pull requests, CI gates, checkpoints, and rollback.

---

## Principle

GitHub is part of Aaroh's engineering system, not a place to store files. The commit history is an audit trail: it should explain how Aaroh was built and make any state recoverable.

Two rules follow from that, and neither is negotiable:

1. **Nothing reaches `main` except through a pull request that passed CI.**
2. **`main` history is never rewritten.** A bad change is reverted, not erased. The failure and its fix both stay in the record.

---

## Branching

Deliberately minimal: `main` plus short-lived branches. No `develop`, `release`, `staging`, or `hotfix` branches — those solve coordination problems a solo project does not have, and they cost real overhead.

| Prefix | Use | Example |
|--------|-----|---------|
| `feature/` | New product capability | `feature/dsa-tracker` |
| `fix/` | Bug fix | `fix/score-confidence-rounding` |
| `chore/` | Tooling, CI, dependencies, repo config | `chore/engineering-foundation` |
| `docs/` | Documentation only | `docs/adr-0061-rls-model` |
| `stage-N/` | A whole build stage | `stage-0/foundation` |

Branches are short-lived. A branch open long enough to need a merge from `main` was scoped too large.

---

## Pull request flow

```
implement on a branch
        ↓
run checks locally
        ↓
push branch, open PR
        ↓
CI: AgentOS baseline · governance · secret scan · dependency audit
        ↓
human review of the PR       ← the approval authority is you, not CI
        ↓
merge into main
        ↓
tag if the merge is a checkpoint
```

The PR body follows [.github/PULL_REQUEST_TEMPLATE.md](../.github/PULL_REQUEST_TEMPLATE.md): problem, scope, architecture impact, AgentOS validation results, quality gates triggered, AI impact, and rollback target.

**An ADR precedes the PR that implements it.** Architectural decisions are not made inside an implementation review. Aaroh's ADRs run from ADR-0057; the next is ADR-0061.

---

## Required checks

| Check | Workflow | Enforces |
|-------|----------|----------|
| AgentOS validation baseline | `ci.yml` | Bootstrap PASS, synthetic 21/21, validator ≥ 83, **0 broken references** |
| Aaroh governance checks | `ci.yml` | ADR-0058 excluded infrastructure, ADR-0059 engine purity, AI gateway isolation, ADR index integrity |
| Secret scan | `security.yml` | No credentials, `.env` files, or key material committed |
| Dependency audit | `security.yml` | No known-vulnerable dependencies |

### On the validator grade

**83/100 is a floor to defend, not a number to raise.** Three validator categories audit AgentOS's own v1.0.0 release rather than Aaroh, and cannot honestly pass here — see [DEVELOPMENT_SETUP.md](./DEVELOPMENT_SETUP.md) §5 and [ADR-0057](../artifacts/decisions/ADR-0057-license-and-source-availability.md). CI checks for *regression*. Raising the score by adding certification paperwork or inventing a licence is gaming the metric, and is explicitly out of bounds.

### What CI cannot check yet

`check_governance.py` reports **ARMED** for engine purity and AI gateway isolation because no application code exists. They begin failing on violation the moment the relevant package appears. QG-005, QG-009, QG-010 and QG-011 remain partly **review** gates: evaluation evidence, golden-file review, and data classification need human judgement. CI narrows what a reviewer must hold in their head; it does not replace them.

---

## GitHub settings (configured outside the repository)

| Setting | Value | Why |
|---------|-------|-----|
| Branch protection on `main` | Enabled | No direct pushes |
| Require pull request | Yes | Every change is reviewable |
| Require status checks | All four above | CI is a gate, not a notification |
| Require branch up to date | Yes | Checks ran against what actually merges |
| Force pushes | Blocked | History is an audit trail |
| Branch deletion | Blocked | |
| Secret scanning + push protection | Enabled | Blocks a secret *before* it reaches the remote — the primary control; `scan_secrets.py` is only a backstop |
| Dependabot alerts | Enabled | |

**Required approvals is set to 0, deliberately.** GitHub does not let a PR author approve their own pull request. On a single-maintainer repository, requiring one approval makes every PR permanently unmergeable except by bypassing protection — which trains you to bypass it. The human approval step is real, it is just enforced by the workflow rather than by a counter. Raise this to 1 the day a second maintainer joins.

---

## Checkpoints and tags

Commits record change; tags record *reachable states*. Tag the merge commit on `main` whenever a stage completes.

| Tag | Meaning |
|-----|---------|
| `v0.1.0-agentos-ready` | Governance layer + CI enforcement in place; no application code |
| `v0.2.0-foundation-complete` | Stage 0 complete |
| `v0.3.0-auth-complete` | Authentication and row isolation working |
| `v0.4.0-dsa-alpha` | DSA tracker |
| `v0.5.0-resume-alpha` | Resume analyzer |
| `v0.6.0-score-engine` | Transparent readiness score + confidence |
| `v0.7.0-decision-engine` | ROI ranking and Daily Mission live |
| `v0.8.0-beta` | Closed beta |
| `v1.0.0-public-release` | Public launch |

```bash
git tag -a v0.1.0-agentos-ready -m "AgentOS governance and CI enforcement in place"
git push origin v0.1.0-agentos-ready
```

Tags are applied **after** merge, to the merge commit on `main` — never to an unmerged branch.

---

## Rollback

Inspect a known-good state:

```bash
git checkout v0.6.0-score-engine
```

Undo a bad merge on `main`:

```bash
git revert -m 1 <merge-commit-sha>
```

`git revert` — never `git reset --hard` or `push --force` on `main`. The revert is itself a reviewable commit, and the original change stays visible for post-mortem. Database migrations do not roll back with code: any PR adding a migration states its undo path in the Rollback section of the PR body.

---

## Cross-references

| Topic | Document |
|-------|----------|
| Commit message format, PR process | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Versioning rules | [VERSION_POLICY.md](../VERSION_POLICY.md) |
| Environment setup | [DEVELOPMENT_SETUP.md](./DEVELOPMENT_SETUP.md) |
| Security policy | [SECURITY.md](../SECURITY.md) |
| Decision index | [context/decisions.md](../context/decisions.md) |
