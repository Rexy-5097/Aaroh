## Pull Request Summary

### What does this PR do?

A clear description of the change and why it is needed.

### Type of Change

- [ ] Documentation update
- [ ] Governance / repository configuration
- [ ] Bug fix (non-breaking — fixes an issue)
- [ ] Feature (non-breaking — adds functionality)
- [ ] Breaking change (causes existing behavior to change)

### Checklist

- [ ] I have read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] This PR makes no claims about behavior that does not exist
- [ ] No secrets, API keys, tokens, or credentials are included
- [ ] No empty directories were added
- [ ] No dead links were introduced
- [ ] An ADR is recorded if an architectural decision was made
- [ ] [CHANGELOG.md](../CHANGELOG.md) is updated
- [ ] Version bumped per [VERSION_POLICY.md](../VERSION_POLICY.md) if applicable

### Aaroh Product Rules

Confirm both, if this PR touches recommendation or scoring logic:

- [ ] Every output this change produces can be traced back to its inputs and reasoning
- [ ] The Career Readiness Score remains a measurement, not the product's goal

### Files Changed

List the key files modified and why.

### Testing

Describe how you verified this change.

---

## Architecture Impact

Tick each that applies, and link the governing ADR.

- [ ] Alters an existing ADR (which — and is a superseding ADR recorded?)
- [ ] API contract / OpenAPI schema
- [ ] Database schema or row-ownership semantics
- [ ] A security or privacy boundary
- [ ] The decision engine (ranking, scoring, confidence, weights)
- [ ] LLM behaviour (prompt, model, provider, output schema)
- [ ] None of the above

> Architectural decisions require an ADR **before** the implementing PR, numbered from ADR-0061 onward, using [templates/decision_record.md](../templates/decision_record.md).

## AgentOS Validation

CI enforces these on every PR. Paste results if you also ran them locally.

```
Bootstrap self-test : 
Synthetic suite     : 
AgentOS validator   : 
Governance checks   : 
Secret scan         : 
```

## Quality Gates

Tick the gates this change triggers, and confirm each is satisfied.

- [ ] QG-005 Security review — auth, secrets, input validation, dependency CVEs
- [ ] QG-009 Decision engine change — purity, weights-as-data, golden files reviewed, trace complete
- [ ] QG-010 Prompt / model change — evaluation evidence, schema validation, PII minimisation, fallback verified
- [ ] QG-011 Privacy / personal data — classification, ownership, minimisation, deletion + export coverage
- [ ] None triggered

## AI Impact

Complete only if this PR touches an LLM path.

```
Provider        : 
Model           : 
Prompt version  : 
Input schema    : 
Output schema   : 
Eval results    : 
PII handling    : 
```

- [ ] The LLM cannot influence ranking, scoring, weights, confidence, or recommendation selection (ADR-0059)
- [ ] The feature degrades to deterministic template output if the provider fails

## Rollback

If this change causes a problem, what gets restored?

```
Restore to tag/commit : 
Revert strategy       : revert the merge commit — never rewrite main history
Data migration to undo: 
```
