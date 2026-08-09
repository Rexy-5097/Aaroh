# Security Policy

> **Layer:** Project | **Version:** 0.0.0 | **Status:** Active

---

## Supported Versions

Aaroh is at **Stage 0 — Pre-Development**. No version has been released, and no application code exists.

| Version | Supported |
|---------|-----------|
| `0.0.0` (pre-development) | Not applicable — nothing is deployed |

A support matrix will be published when the first release is cut.

---

## Reporting a Vulnerability

Even at Stage 0, please report anything security-relevant you find — including accidentally committed credentials, insecure repository configuration, or problems in tooling added later.

### How to Report

1. **Do not** open a public GitHub issue for a security vulnerability.
2. Use GitHub's **private security advisory** feature on this repository (Security → Advisories → Report a vulnerability), or contact the repository maintainer directly.
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix, if known

### What to Expect

- **Acknowledgement:** within 48 hours
- **Initial assessment:** within 5 business days
- **Fix timeline:** depends on severity — critical issues prioritized immediately

These are the maintainer's targets for a pre-release project, not a contractual guarantee.

---

## Security Principles

Aaroh commits to these from Stage 0 onward, before any code is written:

- **No secrets in the repository.** No API keys, tokens, passwords, or credentials are committed, in any branch, at any time. Secret patterns are excluded in [.gitignore](./.gitignore).
- **Student data is sensitive by default.** Aaroh's subject matter is a student's skills, gaps, deadlines, and career prospects. Any future handling of that data is treated as personal data and reviewed accordingly.
- **Transparency does not mean exposure.** Aaroh's requirement to explain its recommendations applies to the user who owns the data — not to third parties.
- **Vendor isolation.** Any future AI provider credentials stay outside core project logic.

---

## Scope

Because no application code exists yet, the current in-scope surface is limited to the repository itself:

| Area | Risk Level |
|------|-----------|
| Committed secrets or credentials | High |
| Repository access and collaborator permissions | Medium |
| Governance and CI configuration added later | Medium |

This table will be expanded as the system is built.

---

## Out of Scope

Reports about features that do not exist yet, or speculative vulnerabilities in an architecture that has not been chosen, cannot be assessed. Please open a normal issue for design concerns instead.
