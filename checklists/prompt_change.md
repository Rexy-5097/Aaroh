# Quality Gate: QG-010 Prompt / Model Change

> **Gate ID:** QG-010 | **Version:** 1.0 (Aaroh-specific, additive to AgentOS 1.x)
> **Owner:** `llm-reviewer` | **Participating Agents:** `security-reviewer`
> **Estimated Runtime:** 20 min | **Gate Severity:** Mandatory
> **Automation Level:** Semi-automatic | **Retry Policy:** Allowed (Max 2 retries, escalates to chief-architect)
> **Required Context:** `standards/llm_integration.md` · `standards/privacy.md`
> **Authority:** `ADR-0059`

---

## Purpose

Ensure that no prompt, model, provider, or schema change ships without evaluation evidence, and that the language model never acquires authority over Aaroh's decisions.

## Entry Criteria

- The change touches a prompt, structured-output schema, provider adapter, model selection, or the AI gateway.
- The evaluation set has been run against both the previous and proposed versions.

---

## Verification Checklist

| Requirement | Verification Method | Evidence Required | Pass Condition |
|-------------|---------------------|-------------------|----------------|
| **Gateway-only access** | Import scan outside the gateway | No provider SDK imported elsewhere | YES (0 violations) |
| **Prompt versioned** | Review prompt registry diff | Version identifier, owner, and diff present | YES |
| **Evaluation evidence** | Compare eval runs | Field-level accuracy for extraction; no regression | YES |
| **Schema validation** | Trace response handling | Every response path validated before state mutation | YES |
| **No ranking authority** | Trace model output flow | Output cannot reach score, ranking, weight, or confidence fields | YES (0 paths) |
| **PII minimisation** | Inspect outbound payload assertion | Test asserts only required fields leave the boundary | YES |
| **Injection containment** | Review handling of document-derived input | Output treated as untrusted; range/enum checked | YES |
| **Provider failure path** | Disable provider, exercise feature | Degrades to deterministic template output | YES |
| **Cost controls** | Review route configuration | Per-user rate and spend caps present | YES |
| **Eval fixture hygiene** | Inspect fixture provenance | No real user personal data in fixtures | YES |

---

## Exit Decision Model

- **PASS:** All requirements met with evidence attached. Score = 100.
- **PASS WITH WARNINGS:** Functional requirements met; eval coverage thin on a secondary field with a scheduled follow-up. Score = 80–99.
- **FAIL:** Missing evaluation evidence, unvalidated response path, SDK imported outside the gateway, unminimised payload, absent fallback, or any path by which model output influences ranking. Score < 80.

---

## Escalation Paths

- **Boundary Violation:** Automatic fail. Escalate to `chief-architect` — this violates `ADR-0059` and cannot be waived.
- **Privacy Conflict:** If a task appears to require more personal data than minimisation allows, escalate jointly to `security-reviewer` and `chief-architect` with the minimal-data alternative stated.
- **Provider Instability:** Repeated schema-compliance failures from a provider escalate to `chief-architect` as a provider-selection decision, not a prompt defect.
