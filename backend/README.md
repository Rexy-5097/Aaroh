# backend

Aaroh's Python backend. At present it contains **one thing**: the sanctioned
database access layer and the test suite that proves user isolation works.

This is Stage 0 vertical slice 1. There is no API, no framework, no ORM, no
authentication, and no product feature. That is deliberate — the isolation
boundary is proven before anything is built on top of it.

## Layout

| Path | Purpose |
|------|---------|
| `app/db/session.py` | The **only** module permitted to create a database connection (ADR-0061 I-12). Owns the pool and the request-scoped transaction that establishes caller identity. |
| `tests/sql/auth_shim.sql` | CI-only. Recreates the pieces of Supabase that already exist in a real project: `auth.users`, `auth.uid()`, the `anon` / `authenticated` roles. **Not production authentication.** |
| `tests/test_rls_isolation.py` | Cross-user isolation, identity-leak, and claim-validation tests. |
| `tests/test_rls_structural.py` | Catalogue assertions that cover every future table automatically. |
| `requirements-dev.txt` | Test dependencies only. Not an application manifest. |

The migration lives at `supabase/migrations/`, per ADR-0062.

## Running the tests

Requires a PostgreSQL instance. CI provides one; locally, point the DSNs at any
throwaway database — the suite drops and recreates `public` and `auth` on every
run, so it is re-runnable and never depends on prior state.

```
export AAROH_TEST_ADMIN_DSN=postgresql://postgres@127.0.0.1:5432/aaroh_test
export AAROH_TEST_APP_DSN=postgresql://aaroh_app:aaroh_app@127.0.0.1:5432/aaroh_test
python -m pytest tests -v
```

`AAROH_TEST_ADMIN_DSN` applies the shim and migrations. `AAROH_TEST_APP_DSN` is
the role the application connects as: no RLS bypass, and `NOINHERIT`, so it
holds no privileges at all until an identity is established.

## What this slice does not do

No Supabase Auth, no JWT verification, no API routes, no clients, no AI, no
decision engine, no schema beyond one table. Those are later slices.
