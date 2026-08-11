-- =============================================================================
-- create_preparation_goals
-- =============================================================================
-- Aaroh's first product table.
--
-- This is the `constraints` input of ADR-0059's engine contract:
--
--     rank(snapshot, constraints, catalog) -> RankedResult
--
-- The product's governing rule is "no recommendation without deadline and
-- time-budget context". Without this row the engine cannot rank anything, so
-- every later capability -- DSA state, resume analysis, the readiness score --
-- depends on it existing first.
--
-- Governed by ADR-0061 section 4 (ownership and RLS), ADR-0062 (raw SQL,
-- forward-only), ADR-0065 (this slice).
-- =============================================================================

CREATE TABLE public.preparation_goals (
    -- One active goal per student, so the owner IS the primary key.
    --
    -- DEFAULT auth.uid() is belt and braces alongside the WITH CHECK policy:
    -- application code never supplies an owner, so it cannot supply the wrong
    -- one, and a future INSERT that forgets the column still lands on the
    -- caller rather than failing open.
    user_id        uuid PRIMARY KEY DEFAULT auth.uid()
                        REFERENCES auth.users (id) ON DELETE CASCADE,

    -- What the student is preparing for. Free text on purpose: a fixed
    -- enumeration of roles would be wrong within a semester, and the engine
    -- treats this as an opaque key until role-specific weighting is designed.
    target_role    text        NOT NULL,

    -- Optional. Company-specific tailoring is a Year-3 concern (moat phase 3);
    -- capturing it now costs nothing and avoids a later migration.
    target_company text,

    -- The date the preparation is aimed at. Temporal validity (must be in the
    -- future) is enforced in the domain layer, not here: a CHECK against now()
    -- is not IMMUTABLE, and a row that was valid when written must not become
    -- invalid merely because time passed.
    deadline       date        NOT NULL,

    -- Hours per week the student can realistically give. 168 is the physical
    -- ceiling; the domain layer applies the tighter, judgement-based bound.
    weekly_hours   smallint    NOT NULL,

    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT preparation_goals_target_role_length
        CHECK (char_length(btrim(target_role)) BETWEEN 1 AND 120),
    CONSTRAINT preparation_goals_target_company_length
        CHECK (target_company IS NULL OR char_length(btrim(target_company)) BETWEEN 1 AND 120),
    CONSTRAINT preparation_goals_weekly_hours_range
        CHECK (weekly_hours BETWEEN 1 AND 168)
);

-- ENABLE alone is insufficient: the table owner bypasses its own policies
-- unless RLS is also FORCED (ADR-0061).
ALTER TABLE public.preparation_goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.preparation_goals FORCE ROW LEVEL SECURITY;

-- USING controls which rows are visible; WITH CHECK controls which rows may be
-- written. USING alone would let a student write a goal owned by someone else.

CREATE POLICY preparation_goals_select_own ON public.preparation_goals
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY preparation_goals_insert_own ON public.preparation_goals
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY preparation_goals_update_own ON public.preparation_goals
    FOR UPDATE TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY preparation_goals_delete_own ON public.preparation_goals
    FOR DELETE TO authenticated
    USING (user_id = auth.uid());

GRANT SELECT, INSERT, UPDATE, DELETE ON public.preparation_goals TO authenticated;
REVOKE ALL ON public.preparation_goals FROM anon;
