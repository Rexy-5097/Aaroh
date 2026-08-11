# Decision Log Index

> **Owner:** All contributors (append) · Chief Architect (curates)
> **Consumers:** All agents (conditional) · All engineers
> **Update Frequency:** Immediately after every architectural decision
> **Max Size:** ~300 tokens — this is an INDEX ONLY
> **Cross-refs:** `artifacts/decisions/` (full ADRs) · `context/state.md` (recent decisions)
> **Rule:** One row per decision. No decision content here. Follow the link for reasoning.

---

## Decision Index

| ID | Title | Status | Date | Impact |
|----|-------|--------|------|--------|
| [ADR-0001](../artifacts/decisions/ADR-0001-rename-knowledge-to-context.md) | Rename `knowledge/` → `context/` | Accepted | 2026-07-02 | Medium |
| [ADR-0002](../artifacts/decisions/ADR-0002-rename-records-to-artifacts.md) | Rename `records/` → `artifacts/` | Accepted | 2026-07-02 | Medium |
| [ADR-0003](../artifacts/decisions/ADR-0003-add-orchestrator-agent.md) | Add Orchestrator agent | Accepted | 2026-07-02 | High |
| [ADR-0004](../artifacts/decisions/ADR-0004-agent-naming-convention.md) | Kebab-case + role-appropriate agent naming | Accepted | 2026-07-02 | Low |
| [ADR-0005](../artifacts/decisions/ADR-0005-vendor-neutral-design.md) | Vendor-neutral design — integrations/ isolation | Accepted | 2026-07-02 | High |
| [ADR-0006](../artifacts/decisions/ADR-0006-context-layer-design.md) | Context layer as operational intelligence, not docs | Accepted | 2026-07-02 | High |
| [ADR-0007](../artifacts/decisions/ADR-0007-token-compression-strategy.md) | Token compression: tables, tags, budgets, archives | Accepted | 2026-07-02 | High |
| [ADR-0008](../artifacts/decisions/ADR-0008-master-workflow-design.md) | Master workflow as orchestrator reference brain | Accepted | 2026-07-02 | High |
| [ADR-0009](../artifacts/decisions/ADR-0009-state-file-as-heartbeat.md) | State file as mandatory-read project heartbeat | Accepted | 2026-07-02 | Medium |
| [ADR-0010](../artifacts/decisions/ADR-0010-workflow-context-separation.md) | context/workflow.md as navigation not summary | Accepted | 2026-07-02 | Medium |
| [ADR-0011](../artifacts/decisions/ADR-0011-standards-hierarchy.md) | Four-tier dependency standards hierarchy | Accepted | 2026-07-02 | High |
| [ADR-0012](../artifacts/decisions/ADR-0012-quality-level-model.md) | Four-level quality model (Min to Flagship) | Accepted | 2026-07-02 | High |
| [ADR-0013](../artifacts/decisions/ADR-0013-metrics-philosophy.md) | Metrics-first philosophy (trends vs snapshots) | Accepted | 2026-07-02 | High |
| [ADR-0014](../artifacts/decisions/ADR-0014-reviewer-question-framework.md) | 10 binary reviewer question checklist | Accepted | 2026-07-02 | High |
| [ADR-0015](../artifacts/decisions/ADR-0015-cross-reference-inheritance.md) | Inheritance-by-reference strategy | Accepted | 2026-07-02 | High |
| [ADR-0016](../artifacts/decisions/ADR-0016-agent-runtime-architecture.md) | Agent runtime architecture | Accepted | 2026-07-02 | High |
| [ADR-0017](../artifacts/decisions/ADR-0017-agent-contract-lifecycle.md) | Agent contract and lifecycle design | Accepted | 2026-07-02 | High |
| [ADR-0018](../artifacts/decisions/ADR-0018-context-loading-strategy.md) | Tiered selective context loading strategy | Accepted | 2026-07-02 | High |
| [ADR-0019](../artifacts/decisions/ADR-0019-escalation-model.md) | Linear, non-circular escalation model | Accepted | 2026-07-02 | High |
| [ADR-0020](../artifacts/decisions/ADR-0020-decision-making-hierarchy.md) | De-escalation & decision-making hierarchy | Accepted | 2026-07-02 | High |
| [ADR-0021](../artifacts/decisions/ADR-0021-standardized-output-format.md) | Standardized output format for reviewers | Accepted | 2026-07-02 | High |
| [ADR-0022](../artifacts/decisions/ADR-0022-token-budget-philosophy.md) | Enforced token budgets (context/output) | Accepted | 2026-07-02 | High |
| [ADR-0023](../artifacts/decisions/ADR-0023-quality-gate-philosophy.md) | Quality gate philosophy (deterministic vs form) | Accepted | 2026-07-02 | High |
| [ADR-0024](../artifacts/decisions/ADR-0024-checklist-design-strategy.md) | Checklist design strategy & gate metadata | Accepted | 2026-07-02 | High |
| [ADR-0025](../artifacts/decisions/ADR-0025-pass-warning-fail-decision-model.md) | Pass/Warning/Fail decision model | Accepted | 2026-07-02 | High |
| [ADR-0026](../artifacts/decisions/ADR-0026-evidence-based-verification.md) | Evidence-based verification requirements | Accepted | 2026-07-02 | High |
| [ADR-0027](../artifacts/decisions/ADR-0027-checklist-sequencing-monitoring.md) | Checklist sequencing & post-release monitoring | Accepted | 2026-07-02 | High |
| [ADR-0028](../artifacts/decisions/ADR-0028-artifact-system-architecture.md) | Artifact system architecture | Accepted | 2026-07-02 | High |
| [ADR-0029](../artifacts/decisions/ADR-0029-global-metadata-schema.md) | Global metadata schema frontmatter standard | Accepted | 2026-07-02 | High |
| [ADR-0030](../artifacts/decisions/ADR-0030-verifiable-document-rules.md) | Verifiable document rules & checks | Accepted | 2026-07-02 | High |
| [ADR-0031](../artifacts/decisions/ADR-0031-artifact-lifecycles-and-archival.md) | Artifact lifecycles & archival policies | Accepted | 2026-07-02 | High |
| [ADR-0032](../artifacts/decisions/ADR-0032-automated-artifact-auditing.md) | Automated artifact auditing in pipelines | Accepted | 2026-07-02 | High |
| [ADR-0033](../artifacts/decisions/ADR-0033-bootstrap-philosophy.md) | Bootstrap philosophy for self-initialization | Accepted | 2026-07-02 | High |
| [ADR-0034](../artifacts/decisions/ADR-0034-one-prompt-initialization-protocol.md) | One-prompt initialization protocol & spec | Accepted | 2026-07-02 | High |
| [ADR-0035](../artifacts/decisions/ADR-0035-minimal-user-knowledge-principle.md) | Minimal user knowledge principle for setups | Accepted | 2026-07-02 | High |
| [ADR-0036](../artifacts/decisions/ADR-0036-project-initialization-workflow.md) | Project initialization & merge workflow | Accepted | 2026-07-02 | High |
| [ADR-0037](../artifacts/decisions/ADR-0037-bootstrap-validation-strategy.md) | Bootstrap validation strategy & metrics | Accepted | 2026-07-02 | High |
| [ADR-0038](../artifacts/decisions/ADR-0038-harness-architecture.md) | Harness modular runtime kernel architecture | Accepted | 2026-07-02 | High |
| [ADR-0039](../artifacts/decisions/ADR-0039-runtime-orchestration.md) | Runtime orchestration and 8-stage SM | Accepted | 2026-07-02 | High |
| [ADR-0040](../artifacts/decisions/ADR-0040-routing-strategy.md) | Routing strategy precedence & policy rules | Accepted | 2026-07-02 | High |
| [ADR-0041](../artifacts/decisions/ADR-0041-context-optimization.md) | Context loading and token size optimization | Accepted | 2026-07-02 | High |
| [ADR-0042](../artifacts/decisions/ADR-0042-execution-planning.md) | Execution planning structured plan objects | Accepted | 2026-07-02 | High |
| [ADR-0043](../artifacts/decisions/ADR-0043-cost-optimization.md) | Cost optimization with caches & early stops | Accepted | 2026-07-02 | High |
| [ADR-0044](../artifacts/decisions/ADR-0044-failure-recovery.md) | Failure recovery loops & escalation limits | Accepted | 2026-07-02 | High |
| [ADR-0045](../artifacts/decisions/ADR-0045-loop-architecture.md) | Loop Engine kernel runtime architecture | Accepted | 2026-07-02 | High |
| [ADR-0046](../artifacts/decisions/ADR-0046-reflection-strategy.md) | Reflection analysis & failure diagnostic reports | Accepted | 2026-07-02 | High |
| [ADR-0047](../artifacts/decisions/ADR-0047-termination-rules.md) | Loop termination stopping rules & conditions | Accepted | 2026-07-02 | High |
| [ADR-0048](../artifacts/decisions/ADR-0048-iteration-policy.md) | Loop modes configuration policy parameters | Accepted | 2026-07-02 | High |
| [ADR-0049](../artifacts/decisions/ADR-0049-quality-thresholds.md) | Quality thresholds scoring evaluation metric | Accepted | 2026-07-02 | High |
| [ADR-0050](../artifacts/decisions/ADR-0050-improvement-strategy.md) | Improvement strategy selector and mode planner | Accepted | 2026-07-02 | High |
| [ADR-0051](../artifacts/decisions/ADR-0051-infinite-loop-prevention.md) | Infinite loop prevention constraints & timeouts | Accepted | 2026-07-02 | High |
| [ADR-0052](../artifacts/decisions/ADR-0052-synthetic-validation-philosophy.md) | Synthetic validation philosophy test suites | Accepted | 2026-07-02 | High |
| [ADR-0053](../artifacts/decisions/ADR-0053-scenario-design-strategy.md) | Scenario design input directories and assertions | Accepted | 2026-07-02 | High |
| [ADR-0054](../artifacts/decisions/ADR-0054-coverage-matrix-design.md) | Coverage matrix mappings for subsystems | Accepted | 2026-07-02 | High |
| [ADR-0055](../artifacts/decisions/ADR-0055-validation-metrics.md) | Validation metrics dashboard parameters | Accepted | 2026-07-02 | High |
| [ADR-0056](../artifacts/decisions/ADR-0056-readiness-criteria.md) | Exit readiness criteria for production releases | Accepted | 2026-07-02 | High |

> ADR-0001 – ADR-0056 are **vendored AgentOS framework decisions**. Aaroh's own decisions begin at ADR-0057.

| ID | Title | Status | Date | Impact |
|----|-------|--------|------|--------|
| [ADR-0057](../artifacts/decisions/ADR-0057-license-and-source-availability.md) | No licence — public repo, all rights reserved | Accepted | 2026-08-10 | High |
| [ADR-0058](../artifacts/decisions/ADR-0058-technology-stack-and-platforms.md) | Stack: Expo + Next.js + FastAPI + Supabase; desktop deferred | Accepted | 2026-08-10 | High |
| [ADR-0059](../artifacts/decisions/ADR-0059-decision-engine-architecture.md) | Decision engine canonical in Python backend as a pure package | Accepted | 2026-08-10 | High |
| [ADR-0060](../artifacts/decisions/ADR-0060-engine-versioning-and-weights.md) | Weights-as-data, versioned traces, golden-file tests | Accepted | 2026-08-10 | High |
| [ADR-0061](../artifacts/decisions/ADR-0061-rls-and-security-boundary.md) | RLS enforced under the caller's identity; service_role never in request path | Accepted | 2026-08-10 | High |
| [ADR-0062](../artifacts/decisions/ADR-0062-migration-strategy.md) | Raw SQL migrations via Supabase CLI; forward-only; RLS DDL never generated | Accepted | 2026-08-10 | High |
| [ADR-0063](../artifacts/decisions/ADR-0063-jwt-verification-and-authentication-boundary.md) | Asymmetric JWT verification via JWKS; VerifiedIdentity; claim minimisation | Accepted | 2026-08-10 | High |
| [ADR-0064](../artifacts/decisions/ADR-0064-http-authentication-boundary.md) | HTTP boundary: dependency-injected identity; uniform 401; no second trust path | Accepted | 2026-08-10 | High |
| [ADR-0065](../artifacts/decisions/ADR-0065-first-product-slice-preparation-goal.md) | First product slice: preparation goal as the engine constraints input | Accepted | 2026-08-10 | High |
| [ADR-0066](../artifacts/decisions/ADR-0066-dsa-activity-record.md) | DSA activity: problem-level append-only record, manual entry only | Accepted | 2026-08-10 | High |
| [ADR-0067](../artifacts/decisions/ADR-0067-readiness-snapshot-contract.md) | Readiness snapshot: immutable point-in-time facts; interpretation stays in the engine | Accepted | 2026-08-11 | High |
| [ADR-0068](../artifacts/decisions/ADR-0068-version-identity-and-immutability.md) | Version identity: immutable human-readable label, SHA-256 byte digest as integrity check; labels never reused | Accepted | 2026-08-12 | High |
| [ADR-0071](../artifacts/decisions/ADR-0071-v1-score-model.md) | V1 score model: ordinal topic weakness by solve rate, 3-activity evidence threshold, equal candidate cost | Accepted | 2026-08-12 | High |
| [ADR-0069](../artifacts/decisions/ADR-0069-dsa-catalogue-contract.md) | DSA-only V1 catalogue: slug identity, TOPICS tags, no time estimate; versioned file, not a table | Accepted | 2026-08-12 | High |

---

## Status Values

`Proposed` · `Accepted` · `Superseded` · `Deprecated`

Superseded decisions are NOT deleted — update status and note the superseding ADR.

---

*Add a row immediately when a decision is made. Full reasoning → `artifacts/decisions/`*
