# Project Workflow

> **Owner:** Project Lead
> **Consumers:** All agents — mandatory read
> **Update Frequency:** Process changes; project type adaptations
> **Max Size:** ~400 tokens
> **Cross-refs:** `workflows/master.md` (full SOPs) · `agents/README.md` (agent roster)
> **Anti-patterns:**
> - Don't duplicate `workflows/master.md` — reference it
> - Don't list implementation details — describe process only
> - Don't let this diverge from how the project actually operates

---

## How This Project Operates

> *One paragraph: the project's operating model. What type of project is this?*

[e.g., "This is an AI research project running in 2-week sprints. Work enters via GitHub issues. Implementation happens in the main coding session. Reviews are routed through the orchestrator. Experiments are logged as they run and validated at sprint close."]

---

## Active Workflows

> Which AgentOS workflows does this project use? Mark active ones.

| Workflow | Status | Notes / Customizations |
|---------|--------|----------------------|
| `workflows/master.md` | ✅ Active | Core orchestration — no customizations |
| `workflows/feature_development.md` | ✅ Active | [Any project-specific deviation] |
| `workflows/bug_fix.md` | ✅ Active | |
| `workflows/research.md` | [✅ / ❌] | [Active only if research project] |
| `workflows/release.md` | ✅ Active | |
| `workflows/incident_response.md` | ✅ Active | |

---

## Project-Specific Deviations

> Deviations from `workflows/master.md` for this project. If none, state "None."

| Workflow | Standard Behavior | This Project's Behavior | Reason |
|---------|-----------------|------------------------|--------|
| [Workflow name] | [What master.md says] | [What this project does instead] | [Why] |

---

## Sprint Cadence

| Field | Value |
|-------|-------|
| Sprint length | [e.g., 2 weeks] |
| Sprint start | [Day of week] |
| Sprint review | [Day before end] |
| Milestone frequency | [e.g., Every 4 sprints] |

---

## Work Intake

> How does work enter the system for this project?

- Source: [GitHub Issues / Jira / Notion / Linear / etc.]
- Format: [Link to issue template or feature proposal]
- Triage: [Who decides priority — name or role]
- Entry into AgentOS: [How tasks move from intake to `context/state.md`]

---

## Agent Customizations

> Project-specific additions to the trigger map from `.agentos/config.yml`.
> If none, state "None — using default trigger map."

| Change Domain | Reviewer | Reason for Override |
|--------------|---------|-------------------|
| [Domain] | [Agent] | [Why different from default] |

---

*Workflow last updated: [DATE]. Deviations from master.md must have written justification above.*
