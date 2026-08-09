# Contributing to Aaroh

> **Layer:** Project | **Version:** 0.0.0 | **Status:** Active

Thank you for contributing to Aaroh — a transparent, constraint-aware career decision engine.

---

## Read This First

Aaroh is at **Stage 0 — Pre-Development**. There is no application code, no chosen architecture, and no dependency set. See [README.md](./README.md) for what currently exists.

Practically, this means:

- **Contributions of application code are not being accepted yet.** The architecture has not been decided, so there is nothing correct to build against.
- Contributions that *are* welcome right now: corrections to documentation, governance improvements, and issues that raise product or design questions.

This will change once AgentOS is installed and the first architecture decisions are recorded.

---

## Governance Model

Aaroh is developed under **AgentOS** governance. Three rules from AgentOS apply to every contribution:

1. **WAT Separation** — Workflows (SOPs), Agents (decisions), and Tools (execution) stay in separate layers. They never bleed into each other.
2. **Architecture First** — Design before building. Review before shipping. Measure before optimizing. No implementation begins without a plan.
3. **Vendor Neutrality** — Core project logic never depends on a specific AI provider. Vendor-specific configuration is isolated.

The AgentOS framework is not yet installed in this repository. Once it is, `AGENTOS.md` at the repository root becomes the authoritative specification and supersedes any conflicting guidance here.

---

## Two Product Rules That Override Convenience

These are specific to Aaroh and apply to every future change:

1. **Transparency is a correctness property, not a feature.** A recommendation that cannot be traced back to its inputs and reasoning is a defect, regardless of how good the recommendation is.
2. **The Career Readiness Score is a measurement, not the product.** Changes that make the score the user-facing goal — rather than an inspectable instrument behind a decision — will be rejected.

---

## Documentation Standards

Every document in this repository must:

1. Include a header blockquote:
   ```markdown
   > **Layer:** [Project | Infrastructure] | **Version:** N.N.N | **Status:** [Draft | Active | Authoritative]
   ```
2. Be written for **token efficiency** — assume an AI agent will read it under context pressure.
3. **Never duplicate** content from another file — cross-reference with a link instead.
4. Use consistent heading structure: `#` for the document title, `##` for major sections, `###` for subsections.
5. Contain **no dead links**. Do not link to files that do not exist yet.
6. Make **no unsupported claims**. Do not describe behavior that has not been built. Mark incomplete sections explicitly:
   ```markdown
   > ⚠️ Draft — not yet validated
   ```

---

## Commit Message Format

```
{type}({scope}): {description}

Types: feat | fix | docs | refactor | standards | agents | checklists | templates | chore
Scope: the directory or component being changed

Examples:
docs(readme): clarify Stage 0 licensing status
chore(github): add issue templates
fix(contributing): correct broken cross-reference
```

---

## Pull Request Process

1. **Open an issue first** for anything significant. Describe the problem before proposing a solution.
2. **Record an ADR** for any architectural decision, using the AgentOS decision record format, once `artifacts/decisions/` exists.
3. **Follow the PR template** at [.github/PULL_REQUEST_TEMPLATE.md](./.github/PULL_REQUEST_TEMPLATE.md).
4. **One reviewer minimum.**
5. **Update [CHANGELOG.md](./CHANGELOG.md)** with the change, and bump the version per [VERSION_POLICY.md](./VERSION_POLICY.md).

---

## Branching

| Branch | Purpose |
|--------|---------|
| `main` | Latest stable state |
| `dev` | Work in progress |

Do not commit directly to `main` once collaborators are active. Open a pull request.

---

## What Will Not Be Accepted

- Application code before the architecture is decided and recorded
- Secrets, API keys, tokens, or credentials of any kind, in any file
- Empty directories created to suggest progress that has not happened
- Documentation describing features that do not exist
- Recommendations logic that cannot explain its own output

---

## Questions

Open a GitHub issue using the [question template](./.github/ISSUE_TEMPLATE/question.md), or see [SUPPORT.md](./SUPPORT.md).

---

*Aaroh CONTRIBUTING.md — Contribution guide.*
