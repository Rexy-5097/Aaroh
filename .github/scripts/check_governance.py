#!/usr/bin/env python3
"""Mechanical enforcement of Aaroh's architecture decisions.

The AgentOS validator enforces QG-001..QG-008 only -- `expected_gates` is
hardcoded in tools/scripts/validate_agentos.py, which the Aaroh project does
not modify. QG-009 (decision engine), QG-010 (prompt/model) and QG-011
(privacy) would therefore be review contracts with no automation behind them.

This script is that automation. It turns the parts of ADR-0059, ADR-0060 and
ADR-0058 that can be checked statically into CI failures.

Checks whose subject does not exist yet report ARMED rather than passing
silently, so it is always visible which guarantees are actually being
enforced today versus waiting for Stage 0 code to appear.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# ── Where the decision engine may live (ADR-0059). Update if Stage 0 differs. ──
ENGINE_CANDIDATE_PATHS = [
    "backend/decision_engine",
    "backend/app/decision_engine",
    "backend/src/decision_engine",
    "packages/decision_engine",
]

# Modules the engine must never import -- each represents a hidden input that
# would destroy determinism, or a boundary violation (ADR-0059).
ENGINE_FORBIDDEN_IMPORTS = {
    # database
    "sqlalchemy", "psycopg", "psycopg2", "asyncpg", "sqlite3", "supabase", "alembic",
    # network
    "requests", "httpx", "aiohttp", "urllib", "urllib3", "socket", "http",
    # AI providers and the gateway itself
    "openai", "anthropic", "cohere", "mistralai", "groq", "together", "litellm",
    "google.generativeai", "boto3",
    # infrastructure explicitly excluded by ADR-0058
    "redis", "celery", "kombu",
}

# Calls that smuggle in hidden, non-reproducible inputs.
ENGINE_FORBIDDEN_CALLS = {
    "datetime.now": "wall-clock time must be passed in as an explicit input",
    "datetime.utcnow": "wall-clock time must be passed in as an explicit input",
    "time.time": "wall-clock time must be passed in as an explicit input",
    "os.getenv": "engine behaviour must not depend on the environment",
    "os.environ.get": "engine behaviour must not depend on the environment",
    "random.random": "randomness must be seeded or absent",
    "random.choice": "randomness must be seeded or absent",
    "random.shuffle": "randomness must be seeded or absent",
    "uuid.uuid4": "non-deterministic identifier generation",
}

# Provider SDKs may only be imported inside the AI gateway.
PROVIDER_SDKS = {
    "openai", "anthropic", "cohere", "mistralai", "groq", "together",
    "litellm", "google.generativeai",
}
GATEWAY_PATH_MARKERS = ("ai/gateway", "ai_gateway", "ai/providers", "gateway/providers")

# Infrastructure excluded until a concrete requirement appears (ADR-0058).
FORBIDDEN_DEPENDENCIES = {"redis", "celery", "kubernetes", "kombu", "arq"}

SEARCH_ROOTS = ["backend", "packages", "apps", "engine"]

# ── ADR-0061: RLS and the data access boundary ────────────────────────────────
# Where migrations will live. Update if Stage 0 chooses a different layout.
MIGRATION_DIRS = ["supabase/migrations", "backend/migrations", "migrations", "db/migrations"]

# I-2: service_role must never appear in request-serving code. ADR-0061 permits
# it for exactly two purposes -- schema migrations and human-initiated
# break-glass -- so migration tooling is the only exemption here. Break-glass is
# a documented human procedure, not committed application code.
SERVICE_ROLE_TOKENS = ("service_role", "SERVICE_ROLE", "SUPABASE_SERVICE_KEY")
SERVICE_ROLE_EXEMPT_MARKERS = ("migrations/",)

# I-8: the AI gateway holds no database credential.
DB_CLIENT_MODULES = {
    "sqlalchemy", "psycopg", "psycopg2", "asyncpg", "sqlite3", "supabase", "alembic",
}

# I-12: the ONLY place a database connection may be created is the sanctioned
# `db/` access layer, which owns the engine and the request-scoped session
# dependency that opens the transaction and applies SET LOCAL. A module that
# builds its own connection has bypassed that wrapper, and therefore I-3.
DB_LAYER_PATH_MARKERS = ("/db/", "/database/")

# EXACTLY the two exemptions ADR-0061 I-12 grants: migration tooling, and the
# test suite (whose RLS tests must open raw connections as different roles --
# proving isolation is the entire point of them).
#
# Do not widen this tuple without amending I-12 first. A `/scripts/` entry was
# removed here after review: it silently exempted backend/scripts/*.py, making
# the implementation more permissive than the decision it enforces.
DB_BOUNDARY_EXEMPT_MARKERS = (
    "/tests/", "/test_", "conftest.py", "migrations/",
)

# Connection factories, checked by call name in addition to imports.
DB_CONNECTION_FACTORIES = {
    "create_engine", "create_async_engine", "async_sessionmaker", "sessionmaker",
    "connect", "create_pool", "create_client", "AsyncConnectionPool", "ConnectionPool",
}

# ── ADR-0063: the authentication boundary ─────────────────────────────────────
# I-16: the verification allow-list is asymmetric-only. HS256 or "none" here
# would re-open algorithm confusion.
FORBIDDEN_JWT_ALGORITHMS = {"HS256", "HS384", "HS512", "none", "None"}

# I-19 / I-23: only the auth package may construct an identity, and production
# must never import the test factory.
IDENTITY_TYPE = "VerifiedIdentity"
AUTH_PACKAGE_MARKERS = ("/app/auth/", "/auth/")
AUTH_TESTING_MODULES = ("app.auth.testing", "auth.testing")

# ADR-0062 (I-13): RLS-sensitive DDL is raw SQL. Python that generates DDL in the
# migrations tree would blind check_rls_migrations, so its presence is a failure.
PY_DDL_MARKERS = (
    "op.create_table", "op.add_column", "op.drop_table", "op.execute",
    "from alembic", "import alembic",
)


class Result:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.lines: list[str] = []

    def ok(self, name: str, detail: str = "") -> None:
        self.lines.append(f"  PASS   {name}{(' — ' + detail) if detail else ''}")

    def armed(self, name: str, detail: str) -> None:
        self.lines.append(f"  ARMED  {name} — {detail}")

    def bad(self, name: str, detail: str) -> None:
        self.lines.append(f"  FAIL   {name} — {detail}")
        self.failures.append(f"{name}: {detail}")


def rel(p: Path) -> str:
    return str(p.relative_to(REPO_ROOT))


def dotted_name(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                found.append((node.module, node.lineno))
    return found


def matches(module: str, forbidden: set[str]) -> str | None:
    root = module.split(".")[0]
    for f in forbidden:
        if module == f or root == f.split(".")[0] and f == root:
            return f
        if module.startswith(f + "."):
            return f
    return None


# ── Check 1: the Aaroh profile is wired up ────────────────────────────────────
def check_profile(r: Result) -> None:
    profile = REPO_ROOT / "profiles" / "aaroh.yaml"
    config = REPO_ROOT / "PROJECT_CONFIG.yaml"
    if not profile.exists():
        r.bad("aaroh profile", "profiles/aaroh.yaml is missing")
        return
    text = config.read_text(encoding="utf-8") if config.exists() else ""
    if "profile: aaroh" not in text:
        r.bad("aaroh profile", "PROJECT_CONFIG.yaml does not select the aaroh profile")
        return

    missing = []
    for line in profile.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("- ") and ("standards/" in line or "agents/" in line):
            target = line[2:].split("#")[0].strip()
            if target and not (REPO_ROOT / target).exists():
                missing.append(target)
    if missing:
        r.bad("aaroh profile", f"references missing files: {', '.join(missing)}")
    else:
        r.ok("aaroh profile", "loads and all referenced standards/agents exist")


# ── Check 2: every ADR is indexed (traceability) ──────────────────────────────
def check_adr_index(r: Result) -> None:
    decisions_dir = REPO_ROOT / "artifacts" / "decisions"
    index = REPO_ROOT / "context" / "decisions.md"
    if not decisions_dir.exists() or not index.exists():
        r.bad("ADR index", "artifacts/decisions/ or context/decisions.md is missing")
        return
    index_text = index.read_text(encoding="utf-8")
    orphans = [
        f.name for f in sorted(decisions_dir.glob("ADR-*.md"))
        if f.name.split("-")[0] + "-" + f.name.split("-")[1] not in index_text
    ]
    if orphans:
        r.bad("ADR index", f"not indexed in context/decisions.md: {', '.join(orphans)}")
    else:
        count = len(list(decisions_dir.glob("ADR-*.md")))
        r.ok("ADR index", f"all {count} ADRs indexed")


# ── Check 3: decision engine purity (ADR-0059) ────────────────────────────────
def check_engine_purity(r: Result) -> None:
    engine_dirs = [REPO_ROOT / p for p in ENGINE_CANDIDATE_PATHS if (REPO_ROOT / p).is_dir()]
    if not engine_dirs:
        r.armed(
            "engine purity (ADR-0059)",
            "no decision engine package found yet; activates at "
            + " | ".join(ENGINE_CANDIDATE_PATHS),
        )
        return

    violations: list[str] = []
    files = 0
    for d in engine_dirs:
        for py in d.rglob("*.py"):
            files += 1
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except SyntaxError as e:
                violations.append(f"{rel(py)}: unparseable ({e})")
                continue

            for module, lineno in imported_modules(tree):
                hit = matches(module, ENGINE_FORBIDDEN_IMPORTS)
                if hit:
                    violations.append(
                        f"{rel(py)}:{lineno} imports '{module}' — engine must not touch "
                        "database, network, or AI layers"
                    )

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = dotted_name(node.func)
                    for bad_call, why in ENGINE_FORBIDDEN_CALLS.items():
                        if name == bad_call or name.endswith("." + bad_call):
                            violations.append(f"{rel(py)}:{node.lineno} calls {name}() — {why}")

    if violations:
        for v in violations:
            r.bad("engine purity (ADR-0059)", v)
    else:
        r.ok("engine purity (ADR-0059)", f"{files} file(s) clean")


# ── Check 4: provider SDKs only inside the AI gateway ─────────────────────────
def check_gateway_isolation(r: Result) -> None:
    roots = [REPO_ROOT / p for p in SEARCH_ROOTS if (REPO_ROOT / p).is_dir()]
    if not roots:
        r.armed(
            "AI gateway isolation",
            "no application source tree yet; activates when backend/ or packages/ appears",
        )
        return

    violations: list[str] = []
    for root in roots:
        for py in root.rglob("*.py"):
            path_str = rel(py).replace("\\", "/")
            if any(marker in path_str for marker in GATEWAY_PATH_MARKERS):
                continue
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for module, lineno in imported_modules(tree):
                if matches(module, PROVIDER_SDKS):
                    violations.append(
                        f"{rel(py)}:{lineno} imports provider SDK '{module}' outside the AI gateway"
                    )

    if violations:
        for v in violations:
            r.bad("AI gateway isolation", v)
    else:
        r.ok("AI gateway isolation", "no provider SDK imported outside the gateway")


# ── Check 5: excluded infrastructure has not crept in (ADR-0058) ──────────────
def check_forbidden_dependencies(r: Result) -> None:
    manifests: list[Path] = []
    for pattern in ("requirements*.txt", "pyproject.toml", "package.json"):
        manifests.extend(
            p for p in REPO_ROOT.rglob(pattern)
            if ".git" not in p.parts and "node_modules" not in p.parts and ".venv" not in p.parts
        )
    # tools/requirements.txt is the vendored AgentOS toolchain, not an Aaroh manifest.
    manifests = [m for m in manifests if rel(m) != "tools/requirements.txt"]

    if not manifests:
        r.armed("excluded infrastructure (ADR-0058)", "no application dependency manifest yet")
        return

    violations: list[str] = []
    for m in manifests:
        text = m.read_text(encoding="utf-8")
        names: set[str] = set()
        if m.name == "package.json":
            try:
                data = json.loads(text)
                for key in ("dependencies", "devDependencies"):
                    names.update(data.get(key, {}).keys())
            except json.JSONDecodeError:
                continue
        else:
            for line in text.splitlines():
                line = line.strip().lower()
                if line and not line.startswith("#"):
                    names.add(line.split("=")[0].split(">")[0].split("<")[0].split("[")[0].strip(' "\''))
        for dep in names:
            root = dep.split("/")[-1].lower()
            if root in FORBIDDEN_DEPENDENCIES:
                violations.append(
                    f"{rel(m)} declares '{dep}' — excluded by ADR-0058 until a concrete "
                    "requirement exists; supersede the ADR first"
                )

    if violations:
        for v in violations:
            r.bad("excluded infrastructure (ADR-0058)", v)
    else:
        r.ok("excluded infrastructure (ADR-0058)", f"{len(manifests)} manifest(s) clean")


# ── Check 6: every user-owned table ships with RLS (ADR-0061 I-5) ─────────────
def check_rls_migrations(r: Result) -> None:
    dirs = [REPO_ROOT / d for d in MIGRATION_DIRS if (REPO_ROOT / d).is_dir()]
    if not dirs:
        r.armed(
            "RLS on new tables (ADR-0061 I-5)",
            "no migrations directory yet; activates at " + " | ".join(MIGRATION_DIRS),
        )
        return

    violations: list[str] = []
    checked = 0

    # ADR-0062 I-13. This check reads SQL. If migrations become Python that
    # generates DDL, the scan below would find no CREATE TABLE and report
    # compliance while unprotected tables ship. Detect that condition rather
    # than being silently blinded by it.
    for d in dirs:
        for py in d.rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            if any(marker in text for marker in PY_DDL_MARKERS):
                violations.append(
                    f"{rel(py)} generates DDL from Python — ADR-0062 mandates raw SQL for "
                    "RLS-sensitive DDL, because generated DDL cannot be verified by this check"
                )

    for d in dirs:
        for sql in sorted(d.rglob("*.sql")):
            text = sql.read_text(encoding="utf-8")
            # Normalise whitespace before matching. A literal substring match
            # treats `FORCE  ROW LEVEL SECURITY` (aligned with two spaces) or a
            # statement wrapped across lines as absent, so a compliant migration
            # would fail -- and, far worse, an author could satisfy the check's
            # letter while evading it. This HARDENS the check; it does not relax
            # any requirement below.
            lowered = " ".join(text.lower().split())
            if "create table" not in lowered:
                continue
            checked += 1
            # A migration that creates a table must, in the same file, enable
            # and force RLS and define at least one policy. A table exposed for
            # even one deploy is a table that leaked.
            if "enable row level security" not in lowered:
                violations.append(f"{rel(sql)} creates a table without ENABLE ROW LEVEL SECURITY")
            if "force row level security" not in lowered:
                violations.append(
                    f"{rel(sql)} creates a table without FORCE ROW LEVEL SECURITY "
                    "(the table owner would bypass its own policies)"
                )
            if "create policy" not in lowered:
                violations.append(f"{rel(sql)} creates a table with no policy defined")
            if "create policy" in lowered and "with check" not in lowered:
                violations.append(
                    f"{rel(sql)} defines policies without WITH CHECK "
                    "(USING alone permits writing rows owned by another user)"
                )
            if "disable row level security" in lowered:
                violations.append(
                    f"{rel(sql)} disables row level security — never permitted (I-10)"
                )

    if violations:
        for v in violations:
            r.bad("RLS on new tables (ADR-0061 I-5)", v)
    else:
        r.ok("RLS on new tables (ADR-0061 I-5)", f"{checked} table-creating migration(s) compliant")


# ── Check 7: service_role stays out of request-serving code (I-2) ─────────────
def check_service_role_isolation(r: Result) -> None:
    roots = [REPO_ROOT / p for p in SEARCH_ROOTS if (REPO_ROOT / p).is_dir()]
    if not roots:
        r.armed("service_role isolation (ADR-0061 I-2)", "no application source tree yet")
        return

    violations: list[str] = []
    for root in roots:
        for src in root.rglob("*.py"):
            path_str = rel(src).replace("\\", "/")
            if any(m in path_str for m in SERVICE_ROLE_EXEMPT_MARKERS):
                continue
            for lineno, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                for token in SERVICE_ROLE_TOKENS:
                    if token in line:
                        violations.append(
                            f"{rel(src)}:{lineno} references '{token}' — service_role bypasses "
                            "RLS and must never appear in request-serving code"
                        )
                        break

    if violations:
        for v in violations:
            r.bad("service_role isolation (ADR-0061 I-2)", v)
    else:
        r.ok("service_role isolation (ADR-0061 I-2)", "no service_role reference in app code")


# ── Check 8: the AI gateway holds no database credential (I-8) ────────────────
def check_gateway_has_no_db(r: Result) -> None:
    roots = [REPO_ROOT / p for p in SEARCH_ROOTS if (REPO_ROOT / p).is_dir()]
    gateway_files = []
    for root in roots:
        for src in root.rglob("*.py"):
            path_str = rel(src).replace("\\", "/")
            if any(marker in path_str for marker in GATEWAY_PATH_MARKERS):
                gateway_files.append(src)

    if not gateway_files:
        r.armed("AI gateway has no DB credential (ADR-0061 I-8)", "no AI gateway module yet")
        return

    violations: list[str] = []
    for src in gateway_files:
        try:
            tree = ast.parse(src.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for module, lineno in imported_modules(tree):
            if matches(module, DB_CLIENT_MODULES):
                violations.append(
                    f"{rel(src)}:{lineno} imports database client '{module}' — the AI gateway "
                    "must have no path to user data"
                )

    if violations:
        for v in violations:
            r.bad("AI gateway has no DB credential (ADR-0061 I-8)", v)
    else:
        r.ok("AI gateway has no DB credential (ADR-0061 I-8)", f"{len(gateway_files)} file(s) clean")


# ── Check 9: connections only in the sanctioned db/ layer (ADR-0061 I-12) ─────
def check_db_access_boundary(r: Result) -> None:
    roots = [REPO_ROOT / p for p in SEARCH_ROOTS if (REPO_ROOT / p).is_dir()]
    if not roots:
        r.armed(
            "DB access boundary (ADR-0061 I-12)",
            "no application source tree yet; activates when backend/ or packages/ appears",
        )
        return

    violations: list[str] = []
    scanned = 0
    for root in roots:
        for src in root.rglob("*.py"):
            path_str = "/" + rel(src).replace("\\", "/")
            if any(m in path_str for m in DB_BOUNDARY_EXEMPT_MARKERS):
                continue
            if any(m in path_str for m in DB_LAYER_PATH_MARKERS):
                continue  # this IS the sanctioned layer
            scanned += 1
            try:
                tree = ast.parse(src.read_text(encoding="utf-8"))
            except SyntaxError:
                continue

            for module, lineno in imported_modules(tree):
                if matches(module, DB_CLIENT_MODULES):
                    violations.append(
                        f"{rel(src)}:{lineno} imports database client '{module}' outside the "
                        "sanctioned db/ layer — sessions must come from the request-scoped "
                        "dependency that applies SET LOCAL (I-3)"
                    )

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = dotted_name(node.func)
                    leaf = name.split(".")[-1]
                    if leaf in DB_CONNECTION_FACTORIES and name != "connect":
                        violations.append(
                            f"{rel(src)}:{node.lineno} calls {name}() outside the sanctioned "
                            "db/ layer — only that layer may create connections (I-12)"
                        )

    if violations:
        for v in violations:
            r.bad("DB access boundary (ADR-0061 I-12)", v)
    else:
        r.ok("DB access boundary (ADR-0061 I-12)", f"{scanned} file(s) outside db/ clean")


# ── Check 10: signature verification is never disabled (ADR-0063 I-15) ────────
def _literal_false(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def check_jwt_verification_not_disabled(r: Result) -> None:
    roots = [REPO_ROOT / p for p in SEARCH_ROOTS if (REPO_ROOT / p).is_dir()]
    if not roots:
        r.armed("JWT verification enabled (ADR-0063 I-15)", "no application source tree yet")
        return

    violations: list[str] = []
    scanned = 0
    for root in roots:
        for src in root.rglob("*.py"):
            path_str = "/" + rel(src).replace("\\", "/")
            if any(m in path_str for m in DB_BOUNDARY_EXEMPT_MARKERS):
                continue
            scanned += 1
            try:
                tree = ast.parse(src.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                # options={"verify_signature": False} and friends
                if isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if (
                            isinstance(key, ast.Constant)
                            and isinstance(key.value, str)
                            and key.value.startswith("verify_")
                            and _literal_false(value)
                        ):
                            violations.append(
                                f"{rel(src)}:{node.lineno} disables {key.value!r} -- "
                                "cryptographic verification may never be turned off"
                            )
                # verify_signature=False as a keyword argument
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg and kw.arg.startswith("verify_") and _literal_false(kw.value):
                            violations.append(
                                f"{rel(src)}:{node.lineno} passes {kw.arg}=False"
                            )
                    # decoding without verifying at all
                    name = dotted_name(node.func)
                    if name.endswith("get_unverified_claims") or name.endswith("decode_complete"):
                        violations.append(
                            f"{rel(src)}:{node.lineno} calls {name}() -- decodes without verifying"
                        )

    if violations:
        for v in violations:
            r.bad("JWT verification enabled (ADR-0063 I-15)", v)
    else:
        r.ok("JWT verification enabled (ADR-0063 I-15)", f"{scanned} file(s) clean")


# ── Check 11: algorithm allow-list stays asymmetric (ADR-0063 I-16) ───────────
def check_jwt_algorithm_allow_list(r: Result) -> None:
    roots = [REPO_ROOT / p for p in SEARCH_ROOTS if (REPO_ROOT / p).is_dir()]
    if not roots:
        r.armed("JWT algorithm allow-list (ADR-0063 I-16)", "no application source tree yet")
        return

    violations: list[str] = []
    for root in roots:
        for src in root.rglob("*.py"):
            path_str = "/" + rel(src).replace("\\", "/")
            if any(m in path_str for m in DB_BOUNDARY_EXEMPT_MARKERS):
                continue
            try:
                tree = ast.parse(src.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                # any list/tuple/set of algorithm strings containing a symmetric one
                if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
                    values = {
                        e.value for e in node.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    }
                    bad = values & FORBIDDEN_JWT_ALGORITHMS
                    # only flag collections that are plainly algorithm lists
                    if bad and (values & {"ES256", "RS256", "ES384", "RS384"} or "alg" in src.read_text(encoding="utf-8")[:400]):
                        violations.append(
                            f"{rel(src)}:{node.lineno} algorithm list contains {sorted(bad)} -- "
                            "symmetric algorithms re-open algorithm confusion"
                        )

    if violations:
        for v in violations:
            r.bad("JWT algorithm allow-list (ADR-0063 I-16)", v)
    else:
        r.ok("JWT algorithm allow-list (ADR-0063 I-16)", "asymmetric only")


# ── Check 12: identity construction is confined to auth (ADR-0063 I-19) ───────
def check_identity_construction(r: Result) -> None:
    roots = [REPO_ROOT / p for p in SEARCH_ROOTS if (REPO_ROOT / p).is_dir()]
    if not roots:
        r.armed("VerifiedIdentity construction (ADR-0063 I-19)", "no application source tree yet")
        return

    violations: list[str] = []
    for root in roots:
        for src in root.rglob("*.py"):
            path_str = "/" + rel(src).replace("\\", "/")
            if any(m in path_str for m in AUTH_PACKAGE_MARKERS):
                continue  # the sanctioned package
            if any(m in path_str for m in DB_BOUNDARY_EXEMPT_MARKERS):
                continue  # tests obtain identities from the sanctioned factory
            try:
                tree = ast.parse(src.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and dotted_name(node.func).endswith(IDENTITY_TYPE):
                    violations.append(
                        f"{rel(src)}:{node.lineno} constructs {IDENTITY_TYPE} outside the "
                        "authentication package -- identities must come from verification"
                    )

    if violations:
        for v in violations:
            r.bad("VerifiedIdentity construction (ADR-0063 I-19)", v)
    else:
        r.ok("VerifiedIdentity construction (ADR-0063 I-19)", "confined to the auth package")


# ── Check 13: production never imports the test factory (ADR-0063 I-23) ───────
def check_auth_testing_not_imported_by_production(r: Result) -> None:
    roots = [REPO_ROOT / p for p in SEARCH_ROOTS if (REPO_ROOT / p).is_dir()]
    if not roots:
        r.armed("auth.testing containment (ADR-0063 I-23)", "no application source tree yet")
        return

    violations: list[str] = []
    for root in roots:
        for src in root.rglob("*.py"):
            path_str = "/" + rel(src).replace("\\", "/")
            if any(m in path_str for m in DB_BOUNDARY_EXEMPT_MARKERS):
                continue  # the test suite is its only permitted consumer
            if path_str.endswith("/app/auth/testing.py"):
                continue  # the module itself
            try:
                tree = ast.parse(src.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for module, lineno in imported_modules(tree):
                if module in AUTH_TESTING_MODULES or module.endswith(".auth.testing"):
                    violations.append(
                        f"{rel(src)}:{lineno} imports {module} -- the test identity factory "
                        "hands out identities without verification and must never ship"
                    )
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("auth"):
                    for alias in node.names:
                        if alias.name == "testing":
                            violations.append(
                                f"{rel(src)}:{node.lineno} imports the test identity factory"
                            )

    if violations:
        for v in violations:
            r.bad("auth.testing containment (ADR-0063 I-23)", v)
    else:
        r.ok("auth.testing containment (ADR-0063 I-23)", "not imported by production code")


def main() -> int:
    r = Result()
    print("Aaroh governance checks")
    print("=" * 60)

    check_profile(r)
    check_adr_index(r)
    check_engine_purity(r)
    check_gateway_isolation(r)
    check_forbidden_dependencies(r)
    check_rls_migrations(r)
    check_service_role_isolation(r)
    check_gateway_has_no_db(r)
    check_db_access_boundary(r)
    check_jwt_verification_not_disabled(r)
    check_jwt_algorithm_allow_list(r)
    check_identity_construction(r)
    check_auth_testing_not_imported_by_production(r)

    for line in r.lines:
        print(line)
    print("=" * 60)

    if r.failures:
        for f in r.failures:
            print(f"::error::{f}")
        print(f"Governance checks FAILED ({len(r.failures)} problem(s))")
        return 1

    print("Governance checks PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
