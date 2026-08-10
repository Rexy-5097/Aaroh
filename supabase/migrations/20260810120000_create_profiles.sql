-- =============================================================================
-- 20260810120000_create_profiles
-- =============================================================================
-- Aaroh's first table. Deliberately minimal: it exists to prove the ownership
-- and isolation model end to end, not to model a user profile.
--
-- Governed by:
--   ADR-0061 section 4 - every user-owned table: canonical user_id, RLS enabled AND
--                  forced, both USING and WITH CHECK, anon denied.
--   ADR-0062    -- raw SQL, timestamp-ordered, forward-only, committed to git.
--
-- auth.users and auth.uid() are NOT created here. They already exist in a
-- Supabase project; CI recreates them via backend/tests/sql/auth_shim.sql.
-- =============================================================================

CREATE TABLE public.profiles (
    -- Canonical ownership column (ADR-0061 section 4). One profile per auth user, so
    -- user_id is itself the primary key.
    user_id      uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
    display_name text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

-- ENABLE alone is not sufficient: a table's owner bypasses its own policies
-- unless RLS is also FORCED. Omitting FORCE is a silent, common gap (ADR-0061).
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles FORCE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- Policies
-- -----------------------------------------------------------------------------
-- USING controls which rows are visible; WITH CHECK controls which rows may be
-- written. USING alone would let a user INSERT or UPDATE a row owned by someone
-- else - the second most common RLS mistake after omitting FORCE.

CREATE POLICY profiles_select_own ON public.profiles
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY profiles_insert_own ON public.profiles
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY profiles_update_own ON public.profiles
    FOR UPDATE TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY profiles_delete_own ON public.profiles
    FOR DELETE TO authenticated
    USING (user_id = auth.uid());

-- -----------------------------------------------------------------------------
-- Grants
-- -----------------------------------------------------------------------------
-- Policies filter rows; grants decide whether the role may touch the table at
-- all. Both are required - a policy without a grant denies, and a grant
-- without a policy under enabled RLS also denies. Default posture is deny.

GRANT SELECT, INSERT, UPDATE, DELETE ON public.profiles TO authenticated;
REVOKE ALL ON public.profiles FROM anon;
