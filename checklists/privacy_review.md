# Quality Gate: QG-011 Privacy / Personal Data Change

> **Gate ID:** QG-011 | **Version:** 1.0 (Aaroh-specific, additive to AgentOS 1.x)
> **Owner:** `security-reviewer` | **Participating Agents:** `llm-reviewer`
> **Estimated Runtime:** 15 min | **Gate Severity:** Mandatory
> **Automation Level:** Manual | **Retry Policy:** Allowed (Max 2 retries, escalates to chief-architect)
> **Required Context:** `standards/privacy.md` · `standards/security.md`

---

## Purpose

Ensure every new personal-data field is classified, justified, isolated, minimised, and covered by deletion and export before it is persisted. This gate exists because retrofitting privacy costs an order of magnitude more than designing it in.

## Entry Criteria

- The change adds or modifies a persisted user-data field, a user-owned table, a storage path, an analytics event, or an external data flow.

---

## Verification Checklist

| Requirement | Verification Method | Evidence Required | Pass Condition |
|-------------|---------------------|-------------------|----------------|
| **Classification** | Review field definitions | Every new field marked High / Medium / Low | YES (0 unclassified) |
| **Justification** | Review change rationale | Each field maps to a specific feature requirement | YES |
| **Ownership semantics** | Review table definition | Explicit owner column and row-isolation policy declared | YES |
| **Server-side ownership check** | Trace access path | Ownership verified server-side, never from client-supplied ID | YES |
| **Signed URL ordering** | Review storage access code | Ownership checked before the URL is signed; lifetime in minutes | YES |
| **Minimisation** | Inspect external payloads | Only structurally required fields leave the boundary | YES |
| **Analytics hygiene** | Inspect analytics payload | Pseudonymous IDs only; no High-class field present | YES |
| **Audit logging** | Trace High-class access | Access logged; audit table append-only | YES |
| **Deletion coverage** | Review deletion path | New data genuinely removed; audit rows pseudonymised | YES |
| **Export coverage** | Review export path | New data included in user export | YES |
| **Retention** | Review data policy | Retention period stated for the new data | YES |
| **No overclaiming** | Review user-facing copy | No claim of anonymity where only identifiers were stripped | YES |

---

## Exit Decision Model

- **PASS:** All fields classified and justified, isolation and minimisation verified, deletion and export cover the new data. Score = 100.
- **PASS WITH WARNINGS:** Hard requirements met; retention period provisional pending a policy decision. Score = 80–99.
- **FAIL:** Any unclassified field, any unjustified collection, ownership inferred from client input, a High-class field in analytics, missing deletion or export coverage, or user-facing copy overclaiming anonymity. Score < 80.

---

## Escalation Paths

- **Unjustified Collection:** Fail the gate. Remove the field or escalate to `chief-architect` with the feature requirement that necessitates it.
- **Isolation Gap:** Any path that could expose one user's data to another is a CRITICAL finding — fail immediately and escalate to `chief-architect`.
- **Minors / Consent:** Any change touching age, consent, or guardianship escalates to `chief-architect`. The DPDP under-18 position is an unresolved decision requiring its own ADR before public launch.
