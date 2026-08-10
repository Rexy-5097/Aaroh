# Project Vision: Aaroh

> **Status:** Active | **Owner:** Rexy-5097
> **Last Modified:** 2026-08-10

---

## 1. Problem Statement

Aaroh is a transparent, constraint-aware career decision engine for CS students. It answers one question — *what is the highest-value use of my next 90 minutes* — and its corollary, *what should I not waste time on*.

The Career Readiness Score is a transparent measurement inside the system, **not the product**. The decision engine is the product.

**Governing law of the architecture:** the deterministic engine **decides**; the LLM only **explains**. See `ADR-0059`.

> **Canonical name:** **Aaroh**. *CareerOS* is the previous working name and appears in the *CareerOS System Design v1.0* PDF, which remains the substantive product specification. Vendored AgentOS framework material is not rewritten for the rename.

## 2. Target Tech Stack

Ratified by `ADR-0058` — full table and rationale in `context/tech_stack.md`.

- Backend: Python + FastAPI (modular monolith; hosts the canonical decision engine)
- Clients: Expo/React Native (mobile), Next.js (web); desktop deferred
- Data: Supabase PostgreSQL, Auth, Storage
- Languages: Python, TypeScript

## 3. Scope & Milestones

- **Stage 0 — Foundation:** monorepo, decision engine (no UI), backend skeleton with row isolation from the first migration, auth, AI gateway stub, CI.
- **Stage 1 — Private Alpha (10–20 testers):** mobile only. DSA tracker, resume analyzer, transparent score + confidence. **No recommender yet.**
- **Stage 2 — Closed Beta (100–200 testers):** web added; ROI ranking, Daily Mission, Decision Streak.
- **Stage 3 — Public launch.**
- **Target Deadline:** UNDECIDED. Working estimate **16–20 weeks**, not the 9 weeks in the prior specification (`ADR-0058`).

## 4. Success Criteria

- **Alpha:** users return unprompted; they understand the score and believe its changes are earned; resume feedback is actionable.
- **Beta:** users repeatedly follow Daily Missions; Decision Accuracy becomes measurable.
- **Long term:** evidence that following Aaroh beats deciding alone. **This is a hypothesis to validate, never a claim to assert.**
