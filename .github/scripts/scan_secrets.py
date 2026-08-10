#!/usr/bin/env python3
"""Backstop secret scan for pull requests.

This is deliberately a BACKSTOP, not the primary control. GitHub's native
secret scanning with push protection is the primary control -- it is free for
public repositories, blocks a push before the secret ever reaches the remote,
and is maintained against a partner list no hand-written regex can match.
Enable it under Settings -> Code security. This script catches the residue and
gives pull requests a visible, blocking check.

No third-party action is used on purpose: a secret scanner runs over every
line of the repository, so adding an unpinned marketplace action here would
trade a small convenience for a real supply-chain exposure.

Never prints a matched value -- only file, line number, and the rule name.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

RULES: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub personal access token", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("GitHub OAuth token", re.compile(r"\bgho_[A-Za-z0-9]{36}\b")),
    ("GitHub fine-grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}")),
    ("OpenAI API key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("Supabase service role JWT", re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{20,}\.")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----")),
    ("Generic assigned credential", re.compile(
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)"
        r"\s*[:=]\s*[\"']?[A-Za-z0-9/+_\-]{16,}[\"']?"
    )),
]

# This file necessarily contains the patterns themselves.
SELF = "\\.github/scripts/scan_secrets\\.py"
SKIP_PATHS = re.compile(rf"^(?:\.git/|\.venv/|node_modules/|{SELF}$)")

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".ico",
    ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".webp", ".so", ".dylib",
}


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line]


def main() -> int:
    findings: list[str] = []
    scanned = 0

    for relpath in tracked_files():
        if SKIP_PATHS.match(relpath):
            continue
        path = REPO_ROOT / relpath
        if not path.is_file() or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        for lineno, line in enumerate(text.splitlines(), 1):
            for rule_name, pattern in RULES:
                if pattern.search(line):
                    # Value intentionally not printed.
                    findings.append(f"{relpath}:{lineno} matched rule '{rule_name}'")

    print(f"Scanned {scanned} tracked text file(s).")

    # Committed environment files are a separate, unambiguous failure.
    env_files = [
        f for f in tracked_files()
        if Path(f).name.startswith(".env") and not Path(f).name.endswith(".example")
    ]
    for f in env_files:
        findings.append(f"{f} — environment file must never be committed")

    key_files = [
        f for f in tracked_files()
        if Path(f).suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".ppk"}
    ]
    for f in key_files:
        findings.append(f"{f} — key material must never be committed")

    if findings:
        print()
        for f in findings:
            print(f"::error::Potential secret: {f}")
        print()
        print(f"Secret scan FAILED ({len(findings)} finding(s)).")
        print("If a finding is a false positive, narrow the rule rather than deleting it.")
        print("If it is real: rotate the credential first, then remove it from history.")
        return 1

    print("Secret scan PASSED — no findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
