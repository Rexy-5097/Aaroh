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


def main() -> int:
    r = Result()
    print("Aaroh governance checks")
    print("=" * 60)

    check_profile(r)
    check_adr_index(r)
    check_engine_purity(r)
    check_gateway_isolation(r)
    check_forbidden_dependencies(r)

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
