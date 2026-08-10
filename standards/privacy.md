# Standard: Privacy and Personal Data

> **Tier:** Cross-cutting — applies to every component that touches user data
> **Owner:** Chief Architect | **Reviewer:** `security-reviewer`
> **Consumers:** `security-reviewer` · `llm-reviewer` (external flows) | **Max:** ~1500 tokens
> **Cross-refs:** `standards/security.md` · `standards/llm_integration.md` · `standards/data_engineering.md` · `checklists/privacy_review.md`

---

## Purpose

Aaroh holds resumes, contact details, employment history, target employers, and a continuous record of a user's career preparation. That is a materially sensitive dataset about people early in their careers, and a leak could damage a user's current employment or prospects. This standard governs what Aaroh collects, how long it keeps it, who it shares it with, and how a user gets it back or gets rid of it.

`standards/security.md` covers *controls* — authn/z, secrets, transport, injection. This standard covers *the data itself*. Both apply.

## Scope

**Governs:** Data classification, minimisation, ownership, retention, deletion, export, audit logging, third-party sharing, analytics pseudonymisation, consent.
**Does NOT govern:** Access-control mechanisms (→ `standards/security.md`), model-boundary rules (→ `standards/llm_integration.md`).

---

## Guiding Principles

1. **Collect the minimum that makes the product work.** Every field must justify itself against a feature.
2. **The user owns their data.** Export and deletion are product features, not compliance chores.
3. **Sharing data with a provider is a decision requiring a reason**, not a default.
4. **Classification precedes storage.** A field whose sensitivity nobody has assessed should not exist.
5. **Retrofitting privacy costs an order of magnitude more than designing it in.**
6. **Do not overclaim.** Stripping identifiers reduces exposure; it does not anonymise.

---

## Data Classification

Every persisted field carries a classification. New fields without one do not pass QG-011.

| Class | Examples | Handling |
|-------|----------|---------|
| **High** | Resume file and contents, email, phone, employment history, target company, target role | Private storage, short-lived signed URLs, ownership-enforced access, audit-logged, minimised before any external call, never in analytics |
| **Medium** | DSA history, readiness scores, recommendation traces, mission outcomes | Ownership-enforced, not shared externally, pseudonymous in analytics |
| **Low** | Aggregate counts, anonymised cohort statistics | Shareable once genuinely aggregated and non-re-identifying |

**Honest limitation.** A resume with name, phone, and email removed is **not anonymous** — employer, institution, dates, and project names remain highly re-identifying. Minimisation reduces exposure; it must never be described to users as anonymisation.

---

## Core Requirements

| Requirement | Rule |
|-------------|------|
| **Ownership** | Every user-owned table has explicit ownership semantics and a row-isolation policy. Ownership is verified server-side on every access — never inferred from a client-supplied identifier. |
| **Minimisation before external calls** | Only fields structurally required by the task leave Aaroh's boundary. Enforced as a pipeline step in code and asserted in tests, not left to convention. |
| **Signed URLs** | Ownership is checked **before** a URL is signed. Lifetimes are minutes, not hours. |
| **Analytics** | Third-party analytics receive pseudonymous identifiers only. No High-class field ever enters analytics. |
| **Audit logging** | Access to High-class data is logged from the first release. Audit tables are append-only — no update or delete grants. |
| **Deletion** | Account deletion genuinely removes user data. Audit records are retained with the subject pseudonymised, resolving the deletion/audit conflict explicitly rather than silently. |
| **Export** | Users can export their own data in a machine-readable form. |
| **Retention** | Every data class has a stated retention period. "Forever by default" is not a retention policy. |
| **Consent** | Consent is obtained where required, recorded with timestamp and version, and revocable. |

---

## Open Compliance Question

Aaroh's stated target user is second- to fourth-year engineering students in India. **Second-year students are routinely 17.** India's DPDP Act 2023 imposes verifiable parental consent for users under 18 and restricts behavioural tracking of children — which a daily-notification career-profiling product plainly engages.

This is **unresolved and requires its own ADR**. It is not a Stage 0 blocker; it **is** a public-launch blocker, and it affects Apple App Privacy and Google Play Data Safety declarations. Do not ship an age-agnostic public release without deciding it.

---

## Anti-patterns

| Anti-pattern | Why It Fails |
|-------------|-------------|
| Collecting a field "we'll probably need it" | Unjustified exposure; grows the breach blast radius |
| Trusting a client-supplied user ID | Direct object reference vulnerability |
| Sending a whole resume when three fields suffice | Unnecessary High-class exposure to a third party |
| Raw user IDs in third-party analytics | Exports identity to a system never designed to hold it |
| Deletion that only hides rows | The promise made to the user is false |
| Signing a storage URL before checking ownership | Access control bypassed by design |
| Long-lived signed URLs | A leaked link is a durable data breach |
| Describing identifier-stripping as anonymisation | Misleads users and regulators |

---

## Reviewer Questions

```
PRIVACY REVIEW CHECKLIST
□ Is every new field classified High / Medium / Low?
□ Does each new field justify itself against a specific feature?
□ Is ownership enforced server-side, independent of client input?
□ Does any new data leave Aaroh's boundary, and is it minimised?
□ Are High-class fields excluded from analytics payloads?
□ Is access to High-class data audit-logged?
□ Is the new data covered by deletion and export paths?
□ Is a retention period stated?
□ Is ownership checked before any storage URL is signed?
□ Does any user-facing copy overclaim anonymity?
```

---

## Completion Criteria

- [ ] All new fields classified and recorded
- [ ] Ownership and isolation verified for new user-owned tables
- [ ] Minimisation asserted in tests for any new external flow
- [ ] Deletion and export cover the new data
- [ ] Retention stated
- [ ] `checklists/privacy_review.md` (QG-011) completed

---

## Cross-references

| Topic | Standard |
|-------|---------|
| Access control, secrets, transport | `standards/security.md` |
| External model boundary | `standards/llm_integration.md` |
| Pipeline and storage practice | `standards/data_engineering.md` |
| Privacy gate | `checklists/privacy_review.md` |
