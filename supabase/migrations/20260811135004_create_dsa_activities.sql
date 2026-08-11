-- =============================================================================
-- create_dsa_activities
-- =============================================================================
-- Aaroh's first source of `snapshot` data (ADR-0066).
--
-- One row records ONE practice event by one student against one problem at one
-- time. Two rows may be identical in every field and still be distinct events:
-- re-solving a problem is signal, not duplication, so there is deliberately NO
-- uniqueness constraint on (user_id, problem_ref).
--
-- Append-only: there is no UPDATE or DELETE policy. A past practice event is a
-- fact, and editing it would corrupt the history the engine will reason over.
-- With RLS enabled and no policy, both are denied by default rather than by a
-- rule someone must remember to apply.
--
-- Governed by ADR-0061 (ownership, RLS), ADR-0062 (raw SQL, forward-only),
-- ADR-0066 (this slice).
-- =============================================================================

CREATE TABLE public.dsa_activities (
    -- Surrogate identity. Nothing else about an activity is unique.
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id        uuid NOT NULL DEFAULT auth.uid()
                        REFERENCES auth.users (id) ON DELETE CASCADE,

    -- The problem as the student typed it. Display only, never grouped on.
    problem_title  text        NOT NULL,

    -- Normalised form of the title: lowercased, whitespace collapsed. This is
    -- the PLATFORM-INDEPENDENT identity of the underlying problem, and the key a
    -- future ingestion layer maps platform ids onto. It does not replace them
    -- and existing rows need no reinterpreting.
    problem_ref    text        NOT NULL,

    -- Aaroh's controlled vocabulary. Held in the DOMAIN layer, not a PostgreSQL
    -- ENUM, so adding a topic is a code change with a test rather than a
    -- migration and a type alteration (ADR-0066 section 4).
    topic          text        NOT NULL,

    -- Closed three-value set that will not change, so unlike topic it also
    -- carries a CHECK: free defence in depth where the vocabulary is stable.
    difficulty     text        NOT NULL,

    -- solved | attempted. Self-reported and unverified -- under manual entry
    -- there is nothing to verify against (ADR-0066 section 3).
    outcome        text        NOT NULL,

    -- Optional: a student recording retrospectively often does not know, and
    -- forcing a number would produce invented ones.
    minutes_spent  smallint,

    -- Metadata only. No allow-list: constraining it would be a decision about
    -- which platforms Aaroh endorses, and no such decision exists.
    platform       text,

    -- When the practice happened, as reported. Distinct from created_at, which
    -- is when Aaroh learned of it.
    occurred_at    timestamptz NOT NULL DEFAULT now(),
    created_at     timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT dsa_activities_problem_title_length
        CHECK (char_length(btrim(problem_title)) BETWEEN 1 AND 200),
    CONSTRAINT dsa_activities_problem_ref_length
        CHECK (char_length(problem_ref) BETWEEN 1 AND 200),
    CONSTRAINT dsa_activities_topic_length
        CHECK (char_length(topic) BETWEEN 1 AND 60),
    CONSTRAINT dsa_activities_difficulty_values
        CHECK (difficulty IN ('easy', 'medium', 'hard')),
    CONSTRAINT dsa_activities_outcome_values
        CHECK (outcome IN ('solved', 'attempted')),
    CONSTRAINT dsa_activities_minutes_range
        CHECK (minutes_spent IS NULL OR minutes_spent BETWEEN 1 AND 600),
    CONSTRAINT dsa_activities_platform_length
        CHECK (platform IS NULL OR char_length(btrim(platform)) BETWEEN 1 AND 60)
);

-- Listing is always "this student's activities, most recent first".
CREATE INDEX dsa_activities_user_occurred_idx
    ON public.dsa_activities (user_id, occurred_at DESC);

ALTER TABLE public.dsa_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dsa_activities FORCE  ROW LEVEL SECURITY;

CREATE POLICY dsa_activities_select_own ON public.dsa_activities
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY dsa_activities_insert_own ON public.dsa_activities
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

-- No UPDATE or DELETE policy, deliberately (ADR-0066 section 9). RLS denies
-- them by default. Account deletion still removes these rows via the FK
-- cascade above, which runs as the deleting role rather than through RLS.

GRANT SELECT, INSERT ON public.dsa_activities TO authenticated;
REVOKE ALL ON public.dsa_activities FROM anon;
