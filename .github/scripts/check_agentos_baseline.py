#!/usr/bin/env python3
"""Assert the AgentOS validation baseline has not regressed.

Runs the three vendored AgentOS validation mechanisms and enforces the
baseline recorded at the Windows -> macOS handoff:

    bootstrap self-test : PASS
    synthetic suite     : 21/21
    validator grade     : >= 83/100
    broken references   : 0

Deliberate design notes:

* The grade is a FLOOR, not a target. 83/100 is expected and correct -- three
  validator categories (Production, Certification, Distribution) audit
  AgentOS's own v1.0.0 release, not Aaroh, and cannot honestly pass here.
  See docs/DEVELOPMENT_SETUP.md section 5. This check exists to catch
  REGRESSION, never to encourage raising the number.

* Broken references are a hard zero. A broken cross-reference is always a
  real defect, unlike the grade.

This script lives in .github/scripts/ rather than tools/scripts/ because
tools/scripts/ is vendored AgentOS framework code and is not modified by
the Aaroh project.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

MIN_GRADE = 83
EXPECTED_SCENARIOS = 21


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, *cmd],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def fail(msg: str) -> None:
    print(f"::error::{msg}")


def main() -> int:
    failures: list[str] = []

    # 1. Bootstrap self-test ------------------------------------------------
    _, out = run(["tools/scripts/bootstrap_project.py", "--self-test"])
    if "[Self-Test] PASS" in out:
        print("bootstrap self-test  : PASS")
    else:
        failures.append("bootstrap self-test did not report PASS")
        print(out)

    # 2. Synthetic validation suite ----------------------------------------
    _, out = run(["validation/runner/execute_suite.py"])
    passed = len(re.findall(r"\|\s*PASS\s*\|", out))
    if passed == EXPECTED_SCENARIOS:
        print(f"synthetic suite      : {passed}/{EXPECTED_SCENARIOS} PASS")
    else:
        failures.append(
            f"synthetic suite: expected {EXPECTED_SCENARIOS} passing scenarios, found {passed}"
        )
        print(out)

    # 3. Main validator -----------------------------------------------------
    _, out = run(["tools/scripts/validate_agentos.py"])

    grade_match = re.search(r"Overall Grade\s*:\s*(\d+)/100", out)
    if not grade_match:
        failures.append("could not parse 'Overall Grade' from validator output")
    else:
        grade = int(grade_match.group(1))
        if grade >= MIN_GRADE:
            print(f"validator grade      : {grade}/100 (floor {MIN_GRADE})")
        else:
            failures.append(
                f"validator grade regressed to {grade}/100, below the {MIN_GRADE} baseline"
            )

    refs_match = re.search(r"Broken References\s*:\s*(\d+)", out)
    if not refs_match:
        failures.append("could not parse 'Broken References' from validator output")
    else:
        refs = int(refs_match.group(1))
        if refs == 0:
            print("broken references    : 0")
        else:
            failures.append(f"{refs} broken cross-reference(s) introduced")
            for line in out.splitlines():
                if "Cross-reference:" in line:
                    print(f"  {line.strip()}")

    print()
    if failures:
        for f in failures:
            fail(f)
        print(f"AgentOS baseline check FAILED ({len(failures)} problem(s))")
        return 1

    print("AgentOS baseline check PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
