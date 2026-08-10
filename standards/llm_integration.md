# Standard: LLM Integration

> **Tier:** Domain — applies to every AI-touching path in Aaroh
> **Owner:** Chief Architect | **Reviewer:** `llm-reviewer`
> **Consumers:** `llm-reviewer` · `security-reviewer` (data flow) | **Max:** ~1500 tokens
> **Cross-refs:** `standards/decision_engine.md` · `standards/security.md` · `standards/privacy.md` · `checklists/prompt_change.md`

---

## Purpose

Govern Aaroh's use of third-party language models so the LLM stays a **rendering layer**, never a decision authority, and so untrusted model output can never reach application state unvalidated.

This standard exists because `standards/ai_ml.md` governs the wrong thing for Aaroh. That standard covers model *training* — seeds, train/test splits, data leakage, experiment tracking, model cards, drift. **Aaroh trains no models.** It calls a hosted API. `standards/ai_ml.md` remains the correct, unmodified standard for AgentOS projects that do train models; it is simply not selected by the Aaroh profile.

## Scope

**Governs:** The AI gateway, provider adapters, prompts, structured-output schemas, response validation, evaluation, PII minimisation at the boundary, provider failure handling, cost and rate-limit controls.
**Does NOT govern:** Ranking or scoring (→ `standards/decision_engine.md`), data classification and retention (→ `standards/privacy.md`), transport and auth (→ `standards/security.md`).

**Authority:** `ADR-0059` (decision/explanation boundary).

---

## Guiding Principles

1. **The LLM explains. It never decides.** This is the single architectural law of the AI layer.
2. **Never trust raw model output.** Validate before it touches state — always.
3. **Everything a model sees is a decision.** Sending data to a provider is a privacy act requiring justification.
4. **Model output is untrusted user input**, because it may be derived from attacker-controlled text.
5. **Prompts are code.** Versioned, owned, reviewed, evaluated before deployment.
6. **The product must work when the provider does not.**

---

## Architectural Rules

| Rule | Requirement |
|------|-------------|
| **Gateway-only access** | All model calls pass through a single entry point (`ai.execute(task, context)`). **No module outside the gateway may import a provider SDK.** |
| **Provider isolation** | Provider specifics live in an adapter behind a stable internal interface. Swapping providers must not change caller code. |
| **Structured output** | Extraction tasks use schema-constrained generation where the provider supports it; the schema is the contract. |
| **Validate before state** | Every response is schema-validated, range-checked, and enum-checked before any persistence. Malformed output is rejected, not coerced. |
| **No authority over ranking** | Model output may never write score, ranking, weight, confidence, or recommendation-selection fields. |
| **Template-first explanation** | Explanations render deterministically from the decision trace. The LLM improves wording only. A provider outage degrades tone, never function. |
| **Trace is the record** | The stored reason for a recommendation is the trace, never generated prose. |

---

## Quality Levels

| Dimension | Minimum Acceptable | Recommended | Production Grade |
|-----------|-------------------|-------------|-----------------|
| Provider access | Gateway exists | + no SDK imports outside gateway | Enforced by CI import check |
| Output validation | Schema validated | + range/enum checks | + rejection metrics monitored |
| Prompt management | Prompts in version control | Versioned with owner | + changelog and rollback |
| Evaluation | Manual spot check | Fixed eval set, run before change | + field-level accuracy vs ground truth |
| PII handling | Direct identifiers stripped | Documented minimisation pipeline | + payload asserted in tests |
| Failure handling | Error surfaced | Graceful degradation | Template fallback; no functional loss |
| Cost control | Rate limited | + per-user daily caps | + spend alerting |

---

## Evaluation Requirements

- A fixed evaluation set exists and is committed **before** the first prompt ships.
- Prompt, model, provider, or schema changes require evaluation evidence **before** deployment.
- **Schema compliance is not correctness.** A schema-valid extraction can still invent a job title. Extraction is measured by **field-level accuracy against ground truth**, not parse success.
- **Eval fixtures may not be real user resumes.** Real resumes are personal data and consent will not exist. Use synthetic, self-authored, or explicitly consented documents, committed sanitised.

---

## Prompt Injection Containment

Resume text is attacker-controlled. Assume every resume may contain instructions aimed at the model.

- Treat all extraction output as **untrusted user data**: validate ranges, enforce enum membership, never persist raw values into privileged fields.
- Extracted values must never write score or ranking fields, directly or transitively.
- Model output must never be used to construct queries, file paths, URLs, or subsequent privileged prompts.
- The blast radius of a successful injection must be bounded to "wrong field values in an extraction record", and that record must be user-correctable.

---

## Anti-patterns

| Anti-pattern | Why It Fails |
|-------------|-------------|
| Importing a provider SDK in a domain module | Lock-in, untestable, bypasses minimisation and validation |
| Letting the model choose the recommendation | Destroys the product's core claim and its testability |
| Persisting generated prose as the reason | The audit trail becomes non-reproducible text |
| Caching explanations by loose input pattern | Stale explanation shown for a different recommendation — trust damage exactly where trust is the product |
| "Temporarily" hardcoding a model name outside the gateway | The temporary version ships |
| Sending the full resume when three fields would do | Unjustified exposure of high-classification data |
| Claiming PII stripping equals anonymisation | Employer + college + dates remain highly re-identifying |
| Blocking the user on a provider call | One outage takes the product down |

---

## Reviewer Questions

```
LLM INTEGRATION REVIEW CHECKLIST
□ Do all model calls route through the gateway?
□ Does any module outside the gateway import a provider SDK?
□ Is the output schema defined, and validated before state is touched?
□ Can model output reach any score, ranking, weight, or confidence field?
□ Is the prompt versioned, owned, and diffed in this change?
□ Is evaluation evidence attached, with field-level accuracy?
□ Is the minimisation pipeline applied, and asserted in a test?
□ Are eval fixtures free of real user personal data?
□ Does the feature degrade to the template path if the provider fails?
□ Are per-user cost and rate caps enforced on this route?
```

---

## Completion Criteria

- [ ] No provider SDK imported outside the gateway
- [ ] Schema validation covers every response path
- [ ] Evaluation run and evidence attached
- [ ] Minimisation asserted on the outbound payload
- [ ] Template fallback verified with the provider unavailable
- [ ] `checklists/prompt_change.md` (QG-010) completed

---

## Cross-references

| Topic | Standard |
|-------|---------|
| Engine boundary and purity | `standards/decision_engine.md` |
| Transport, auth, secrets | `standards/security.md` |
| Data classification and minimisation policy | `standards/privacy.md` |
| Prompt/model change gate | `checklists/prompt_change.md` |
