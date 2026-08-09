# Version Policy

> **Layer:** Project | **Version:** 0.0.0 | **Status:** Authoritative

Adapted from the AgentOS template version policy. Aaroh follows the same rules, applied to a product rather than a framework.

---

## Semantic Versioning

Aaroh follows [Semantic Versioning 2.0.0](https://semver.org/).

```
MAJOR.MINOR.PATCH
```

---

## Version Definitions

### MAJOR (X.0.0)

A breaking change to Aaroh's public behavior, data model, or interfaces.

Examples:
- Changing how the Career Readiness Score is computed in a way that invalidates previous results
- Removing or renaming a public interface that consumers depend on
- A change to stored user data that requires migration

**When incrementing MAJOR:** write a migration note in `CHANGELOG.md` and tag the commit.

### MINOR (0.X.0)

A backward-compatible addition of functionality.

Examples:
- Adding a new input signal to the decision engine
- Adding a new explanation surface
- Adding a new governance document or standard

**When incrementing MINOR:** document in `CHANGELOG.md` and tag the commit.

### PATCH (0.0.X)

A backward-compatible fix or documentation improvement.

Examples:
- Fixing a typo or broken cross-reference
- Correcting a calculation bug that does not change intended behavior
- Clarifying existing documentation

**When incrementing PATCH:** document in `CHANGELOG.md`.

---

## Compatibility Expectations

| Change Type | Compatibility | Migration Required |
|-------------|---------------|--------------------|
| MAJOR | Breaking | Yes — see CHANGELOG |
| MINOR | Backward compatible | No |
| PATCH | Backward compatible | No |

---

## Pre-Release Versions

Aaroh is currently at `0.0.0`, meaning **no functionality has been released**.

During pre-1.0 development, MINOR changes may be breaking. Nothing about Aaroh's behavior should be depended on until `1.0.0`.

Aaroh reaches `1.0.0` when:

- AgentOS governance is installed and passing its own validation
- The architecture is decided and recorded as ADRs
- A working decision engine produces explainable recommendations
- The applicable quality gates pass

---

## Version File

The current version is always stored in [`VERSION`](./VERSION) at the repository root.

Format: plain text, one line, no prefix.

```
0.0.0
```

---

## Branching Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Latest stable state |
| `dev` | Work in progress |

---

*Aaroh VERSION_POLICY.md — Governs all versioning decisions for this project.*
