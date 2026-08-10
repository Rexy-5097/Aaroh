-- =============================================================================
-- CI-ONLY Supabase auth shim
-- =============================================================================
--
-- THIS IS NOT PRODUCTION AUTHENTICATION. It creates nothing that Aaroh ships.
--
-- In a real Supabase project the `auth` schema, `auth.users`, `auth.uid()`, and
-- the `anon` / `authenticated` roles already exist. CI runs plain PostgreSQL,
-- so this file recreates *only* those pre-existing pieces, allowing the RLS
-- suite to exercise real PostgreSQL row-level security semantics.
--
-- Aaroh's own migrations under supabase/migrations/ must NEVER create any of
-- this - in production it is already there.
--
-- -----------------------------------------------------------------------------
-- PINNED ASSUMPTION (ADR-0061, Testing Strategy)
-- -----------------------------------------------------------------------------
-- auth.uid() below is pinned to Supabase's documented definition: read the
-- legacy per-claim GUC `request.jwt.claim.sub` first, then fall back to the
-- `sub` field of the JSON GUC `request.jwt.claims`.
--
-- If Supabase changes this definition and the shim is not updated, the RLS
-- tests will keep passing while production behaves differently. That is a false
-- assurance strictly worse than no test at all. Re-verify this function against
-- a real Supabase development project at every stage boundary.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS auth;

-- Minimal stand-in for Supabase's auth.users. Only the primary key matters
-- here: it is the referent for the canonical ownership column (ADR-0061 section 4).
CREATE TABLE IF NOT EXISTS auth.users (
    id    uuid PRIMARY KEY,
    email text
);

CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(
        NULLIF(current_setting('request.jwt.claim.sub', true), ''),
        (NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
    )::uuid
$$;

-- -----------------------------------------------------------------------------
-- Roles
-- -----------------------------------------------------------------------------
-- `anon` and `authenticated` mirror Supabase's roles.
--
-- `aaroh_app` is the login role the backend connects as (ADR-0061 I-1):
--   NOBYPASSRLS  -- row-level security always applies to it
--   NOINHERIT    -- it holds NO privileges until it explicitly SET ROLEs.
--
-- NOINHERIT is the load-bearing choice. With the default INHERIT, aaroh_app
-- would silently hold `authenticated`'s privileges on every connection, and a
-- query issued outside the sanctioned transaction wrapper would still succeed.
-- With NOINHERIT, "no identity established" means "no access at all", which is
-- a property the test suite asserts directly.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN NOINHERIT;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN NOINHERIT;
    END IF;

    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'aaroh_app') THEN
        -- Test-only credential. CI-local database, never reachable off-host.
        CREATE ROLE aaroh_app LOGIN NOINHERIT NOBYPASSRLS PASSWORD 'aaroh_app';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT USAGE ON SCHEMA auth   TO anon, authenticated;
GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated;

-- aaroh_app may assume either role, but inherits neither (NOINHERIT above).
GRANT anon, authenticated TO aaroh_app;
