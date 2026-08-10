"""Structural RLS assertions (ADR-0061 Tier B).

These are the highest-leverage tests in the suite because they are written
against the catalogue rather than against a table name. Every table Aaroh adds
later is covered the moment it exists -- no test needs updating to protect it.

A table that ships without RLS fails here even if nobody remembered to write a
test for that table.
"""

from __future__ import annotations

# Tables in `public` that are deliberately not user-owned may be listed here.
# Adding a name to this set is a security decision and must be justified in the
# pull request that adds it -- it removes the table from every assertion below.
NON_USER_OWNED_TABLES: set[str] = set()

WRITE_COMMANDS = {"INSERT", "UPDATE", "ALL"}


def _app_tables(admin_conn) -> list[str]:
    rows = admin_conn.execute(
        """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r'
        ORDER BY c.relname
        """
    ).fetchall()
    return [r[0] for r in rows if r[0] not in NON_USER_OWNED_TABLES]


def test_there_is_at_least_one_table_to_check(admin_conn):
    """Guard against the whole suite silently passing on an empty schema."""
    assert _app_tables(admin_conn), "no application tables found; the suite would be vacuous"


def test_every_table_has_rls_enabled_and_forced(admin_conn):
    """ENABLE alone is insufficient -- the table owner bypasses its own
    policies unless RLS is also FORCED."""
    offenders = []
    for table in _app_tables(admin_conn):
        enabled, forced = admin_conn.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE oid = ('public.' || %s)::regclass",
            (table,),
        ).fetchone()
        if not enabled or not forced:
            offenders.append(f"{table}(enabled={enabled}, forced={forced})")
    assert not offenders, f"tables without RLS enabled AND forced: {offenders}"


def test_every_table_has_at_least_one_policy(admin_conn):
    offenders = []
    for table in _app_tables(admin_conn):
        count = admin_conn.execute(
            "SELECT count(*) FROM pg_policies WHERE schemaname = 'public' AND tablename = %s",
            (table,),
        ).fetchone()[0]
        if count == 0:
            offenders.append(table)
    assert not offenders, f"tables with RLS enabled but no policy: {offenders}"


def test_read_policies_have_using_predicates(admin_conn):
    offenders = []
    for table in _app_tables(admin_conn):
        rows = admin_conn.execute(
            "SELECT policyname, cmd, qual FROM pg_policies "
            "WHERE schemaname = 'public' AND tablename = %s",
            (table,),
        ).fetchall()
        for name, cmd, qual in rows:
            if cmd in {"SELECT", "UPDATE", "DELETE", "ALL"} and not qual:
                offenders.append(f"{table}.{name} ({cmd})")
    assert not offenders, f"policies missing a USING predicate: {offenders}"


def test_write_policies_have_with_check_predicates(admin_conn):
    """A write policy without WITH CHECK lets a user create or modify a row
    owned by somebody else."""
    offenders = []
    for table in _app_tables(admin_conn):
        rows = admin_conn.execute(
            "SELECT policyname, cmd, with_check FROM pg_policies "
            "WHERE schemaname = 'public' AND tablename = %s",
            (table,),
        ).fetchall()
        for name, cmd, with_check in rows:
            if cmd in WRITE_COMMANDS and not with_check:
                offenders.append(f"{table}.{name} ({cmd})")
    assert not offenders, f"write policies missing WITH CHECK: {offenders}"


def test_every_table_has_the_canonical_ownership_column(admin_conn):
    """ADR-0061 §4: a single canonical ownership column named user_id."""
    offenders = []
    for table in _app_tables(admin_conn):
        exists = admin_conn.execute(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s AND column_name = 'user_id'",
            (table,),
        ).fetchone()[0]
        if not exists:
            offenders.append(table)
    assert not offenders, f"user-owned tables without a user_id column: {offenders}"


def test_app_role_cannot_bypass_rls(admin_conn):
    """ADR-0061 I-1. If this ever passes to True, every policy above is void."""
    bypass = admin_conn.execute(
        "SELECT rolbypassrls FROM pg_roles WHERE rolname = 'aaroh_app'"
    ).fetchone()
    assert bypass is not None, "aaroh_app role does not exist"
    assert bypass[0] is False, "aaroh_app holds BYPASSRLS -- RLS is not enforced"


def test_app_role_does_not_inherit_privileges(admin_conn):
    """NOINHERIT is what makes 'no identity established' mean 'no access'."""
    inherit = admin_conn.execute(
        "SELECT rolinherit FROM pg_roles WHERE rolname = 'aaroh_app'"
    ).fetchone()[0]
    assert inherit is False, "aaroh_app inherits privileges without SET ROLE"


def test_anon_holds_no_table_privileges(admin_conn):
    offenders = []
    for table in _app_tables(admin_conn):
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            granted = admin_conn.execute(
                "SELECT has_table_privilege('anon', ('public.' || %s)::regclass, %s)",
                (table, privilege),
            ).fetchone()[0]
            if granted:
                offenders.append(f"{table}:{privilege}")
    assert not offenders, f"anon holds privileges it should not: {offenders}"
