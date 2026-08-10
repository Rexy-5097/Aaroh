# Development Setup

> **Layer:** Project | **Version:** 0.0.0 | **Stage:** 0 — Pre-Development | **Status:** Active
>
> How to clone Aaroh on a fresh machine and continue development.
> Written for the Windows → macOS handoff, but machine-agnostic.

---

## What You Are Cloning

Aaroh is at **Stage 0 — Pre-Development**. The repository contains:

- Governance and identity files (README, CONTRIBUTING, SECURITY, etc.)
- The **AgentOS v1.0.0 framework, vendored** — agents, workflows, standards, checklists, templates, runtime, validation suite
- A completed AgentOS **bootstrap** — `PROJECT_CONFIG.yaml`, `context/vision.md`, `context/state.md`

There is **no application code**, no chosen technology stack, and no installed application dependencies. Nothing is missing — that state is intentional and recorded in [CHANGELOG.md](../CHANGELOG.md).

Everything needed to reproduce the project is committed. The only file excluded is `.claude/settings.local.json`, a machine-local editor setting containing one Windows-specific permission entry and no project state.

---

## Prerequisites

| Tool | Required version | Status |
|------|------------------|--------|
| **Git** | any recent | Verified with 2.55.0 |
| **Python** | 3.x — verified on **3.12.10** | Minimum supported version **TBD** (never tested below 3.12) |
| **PyYAML** | `>=6.0` — verified on 6.0.3 | Only third-party dependency in the repo |
| **GitHub CLI (`gh`)** | optional | Used for repo/collaborator operations; verified on 2.97.0 |
| **make** | optional | A `Makefile` is vendored; all targets have direct `python3` equivalents |
| **Node.js** | **TBD** | Not established — no JavaScript in the project |
| **App package manager** | **TBD** | Not established — depends on the stack decision |

> Versions marked **TBD** are genuinely undetermined. They are not defaults awaiting confirmation — the corresponding decision has not been made. Do not invent them.

macOS note: system Python may be older than 3.12. Install a current Python via [python.org](https://www.python.org/downloads/) or `brew install python@3.12`.

---

## 1. Clone

```bash
git clone https://github.com/Rexy-5097/Aaroh.git
cd Aaroh
```

---

## 2. Configure Git Identity

**Do this before your first commit.** Commits authored with the wrong email are attributed to the wrong GitHub account, which previously required rewriting history to correct.

```bash
git config user.name "Rexy-5097"
git config user.email "177911845+Rexy-5097@users.noreply.github.com"
```

The noreply address encodes the GitHub user ID, so it links to the account without any email verification. Personal addresses tried previously either belonged to a different GitHub account or were not verified on this one, and did not attribute correctly. Use the noreply address unless you have confirmed an alternative is verified under Settings → Emails.

---

## 3. Install Dependencies

Only the AgentOS toolchain has dependencies. A virtual environment is recommended but not required.

```bash
python3 -m venv .venv && source .venv/bin/activate
```

```bash
python3 -m pip install -r tools/requirements.txt
```

`.venv/` is gitignored. There are no application dependencies to install, because there is no application.

---

## 4. Environment Variables

**Aaroh currently requires none.** There is no `.env.example`, because there is nothing to template — no secrets, no API keys, no service endpoints exist yet.

One optional variable is supported:

| Variable | Purpose | Required |
|----------|---------|----------|
| `AGENTOS_ROOT` | Overrides the validator's repository-root detection | No — auto-detected |

`.gitignore` already blocks `.env` and `.env.*` while allowing `.env.example`. **When the first real secret appears, create `.env.example` with placeholder values only** and never commit the real file.

---

## 5. Verify the Repository Is Healthy

Run all three AgentOS validation mechanisms. Expected results are listed — anything different means something broke in transit.

```bash
python3 tools/scripts/bootstrap_project.py --self-test
```
Expected: `[Self-Test] PASS. Bootstrap test runs cleanly.`

```bash
python3 validation/runner/execute_suite.py
```
Expected: all 21 scenarios `PASS`, 100% subsystem coverage.

```bash
python3 tools/scripts/validate_agentos.py
```
Expected: **`Overall Grade: 83/100`**, `Broken References: 0`, 27 warnings.

### Why 83/100 and not 100/100

**This is expected. Do not "fix" it.** AgentOS documentation says development requires 100/100, but that gate cannot honestly pass in a downstream project.

Three of the validator's eighteen categories audit *the AgentOS template's own v1.0.0 release*, not the project using it:

| Category | Score | Requires |
|----------|-------|----------|
| Production | 0/100 | `VERSION` = `1.0.0` + AgentOS's RC1 benchmark logs |
| Certification | 0/100 | `VERSION` = exactly `1.0.0` + AgentOS's certification reports |
| Distribution | 35/100 | AgentOS's own release/onboarding docs, CI, devcontainer |

Passing them would require setting Aaroh's `VERSION` to `1.0.0` and committing AgentOS's certification paperwork — asserting that Aaroh is a production-certified v1.0.0 system. Aaroh has no code. The claim would be false, so these are deliberately left failing.

`Structural: 70/100` is likewise expected: `LICENSE` is absent by decision, and `INSTALL.md` was not vendored because it is an unfinished upstream placeholder about installing AgentOS itself.

**Every operational subsystem scores 100/100:** Contract, Dependency, Token Budget, Cross-reference, Architecture, Agent Routing, Workflow, Standards, Metrics, Artifacts, Bootstrap, Harness, Loop, Validation.

---

## 6. Known Upstream AgentOS Defects

Four defects in AgentOS v1.0.0 are **already fixed in this vendored copy**. If you ever re-vendor or update the framework from `Rexy-5097/raptors-way`, these will return:

| # | Defect | Fix applied here |
|---|--------|------------------|
| 1 | `validate_agentos.py` hardcoded `REPO_ROOT` to the framework author's Mac path, so the validator reported every file missing on any other machine | Resolves relative to `__file__`, with `AGENTOS_ROOT` override |
| 2 | `metrics/README.md` and `ADR-0015` contained `file:///Users/...` absolute links | Converted to relative |
| 3 | `TEAM_QUICKSTART.md` linked to `DOCUMENTATION_INDEX.md`, which is not vendored | Link removed |
| 4 | `bootstrap_project.py` omits the required `goals` field when writing `PROJECT_CONFIG.yaml` | Restored by hand |

Also note: `BOOTSTRAP.md`'s profile table disagrees with the actual `profiles/*.yaml` files (it lists `security` for `ai_project`; the YAML has `testing`). **Trust the YAML.**

---

## 7. Re-running Bootstrap (not normally needed)

Bootstrap has already been run and its output is committed. Re-run it only to change the profile:

```bash
python3 tools/scripts/bootstrap_project.py --profile <name> --defaults
```

> ⚠️ `--defaults` writes `framework: Vite React` and `languages: TypeScript, CSS` — a stack nobody has chosen. Pass a config file instead, or correct `PROJECT_CONFIG.yaml` afterward. Bootstrap preserves existing `context/vision.md` and `context/state.md` unless you pass `--resume`.

Current profile is `ai_project`: standards `code_quality`/`ai_ml`/`testing`, agents `orchestrator`/`ai-reviewer`, gates QG-001 through QG-004.

---

## 8. Starting Development

Read [AGENTOS.md](../AGENTOS.md) first — it is the initialization protocol for any AI assistant working in this repository. Then `context/vision.md` and `context/state.md`.

Before writing application code, these decisions must be made and recorded as ADRs:

| Open decision | Blocks |
|---------------|--------|
| **License** | Repo is public with all rights reserved; nobody may legally use it |
| **Technology stack and target platform** | `framework` and `languages` are `UNDECIDED` |
| **Decision-engine architecture** | How recommendations are produced and explained |
| **Career Readiness Score model** | The measurement behind the recommendation |
| **Project deadline** | `UNDECIDED` |

Record each using `templates/decision_record.md` into `artifacts/decisions/`, then index it in `context/decisions.md`.

> **ADR numbering starts at ADR-0057.** ADR-0001 through ADR-0056 are AgentOS's own vendored framework decisions, not Aaroh's.

Two product rules constrain every future change ([CONTRIBUTING.md](../CONTRIBUTING.md)):

1. **Transparency is a correctness property.** A recommendation that cannot be traced to its inputs and reasoning is a defect.
2. **The Career Readiness Score is a measurement, not the product.**

---

## 9. Repository Conventions

| Topic | Reference |
|-------|-----------|
| Contribution rules, commit format | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Versioning | [VERSION_POLICY.md](../VERSION_POLICY.md) |
| Security and vulnerability reporting | [SECURITY.md](../SECURITY.md) |
| Change history | [CHANGELOG.md](../CHANGELOG.md) |
| AgentOS protocol | [AGENTOS.md](../AGENTOS.md) |
| AgentOS quick start | [TEAM_QUICKSTART.md](../TEAM_QUICKSTART.md) |

Line endings are normalized to LF via `.gitattributes`. Running the Python tooling on Windows rewrites generated reports with CRLF, which shows as a modification with zero content change — on macOS this does not occur.

---

*Aaroh — Know what to do next.*
