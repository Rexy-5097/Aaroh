# Changelog

All notable changes to Aaroh are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) per [VERSION_POLICY.md](./VERSION_POLICY.md).

---

## [Unreleased]

### Pending Decisions

- License selection — no license granted until decided
- AgentOS installation and profile selection
- Technology stack and target platform
- Architecture of the decision engine and the Career Readiness Score

---

## [0.0.0] — 2026-08-10 — Repository Initialization

Repository created under AgentOS documentation conventions. **No application code.** Governance and identity files only.

### Added

- `README.md` — product identity, Stage 0 status, licensing notice
- `CONTRIBUTING.md` — contribution rules, commit format, PR process, Aaroh's transparency rules
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1
- `SECURITY.md` — vulnerability reporting policy and Stage 0 security principles
- `SUPPORT.md` — where to get help
- `VERSION_POLICY.md` — semantic versioning rules for this project
- `VERSION` — `0.0.0`
- `.gitignore` — secret, build, data, and OS patterns adapted from the AgentOS template
- `.gitattributes` — LF line-ending normalization, matching `.editorconfig`
- `.editorconfig` — editor formatting consistency
- `.github/CODEOWNERS` — code ownership
- `.github/PULL_REQUEST_TEMPLATE.md` — PR template
- `.github/ISSUE_TEMPLATE/bug_report.md` — bug report template
- `.github/ISSUE_TEMPLATE/feature_request.md` — feature request template
- `.github/ISSUE_TEMPLATE/question.md` — question template
- `.github/LABELS.md` — repository label definitions

### Deliberately Not Added

- `LICENSE` — pending selection; all rights reserved until then
- AgentOS framework files (`AGENTOS.md`, `context/`, `agents/`, `workflows/`, `standards/`, `checklists/`, `templates/`, `artifacts/`, `runtime/`, `validation/`) — installed in the next step
- CI workflows — would reference validation tooling that does not exist yet
- Any application source directories

---

*Aaroh Changelog*
