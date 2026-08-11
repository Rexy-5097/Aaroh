"""The foundational topic ordering (ADR-0070 section 6).

This is a **product decision**, not a derived list: it states where a student
with no history should begin. `ADR-0070` recorded it on 2026-08-12 and is
explicit that the repository did not previously contain it.

Why this lives in its own module
--------------------------------
`TOPICS` in `app.domain.dsa` is *presentation and determinism* order -- its own
comment says so, `ADR-0067` section 6 orders snapshot fields by it purely to make
output byte-identical, and `ADR-0069` section 6 warns that "treating position as
primacy would smuggle a weight into the catalogue".

This ordering means the opposite: position **is** primacy. Keeping the two in
separate modules is what stops someone tidying them into one list and silently
merging two different meanings (`ADR-0070` section 7).

The invariant, enforced at import
---------------------------------
`ADR-0070` section 7.1 names the drift risk: a seventeenth topic added to
`TOPICS` but not here would be silently ignored at cold start. That ADR assigned
the check to "the slice that first represents this ordering in code", which is
this one -- so the permutation is asserted at import time rather than left to a
test someone might not run.
"""

from __future__ import annotations

from app.domain.dsa import TOPICS

# ADR-0070 section 6. Order is meaningful: earlier entries come first for a
# student whose history is insufficient to rank on (ADR-0071 section 4).
FOUNDATIONAL_ORDER: tuple[str, ...] = (
    "arrays",
    "strings",
    "hash-tables",
    "two-pointers",
    "sliding-window",
    "sorting",
    "binary-search",
    "linked-lists",
    "stacks-and-queues",
    "recursion-and-backtracking",
    "trees",
    "heaps",
    "graphs",
    "greedy",
    "dynamic-programming",
    "math-and-bit-manipulation",
)


def _verify_permutation() -> None:
    """Fail loudly at import if the two lists have drifted apart."""
    if len(set(FOUNDATIONAL_ORDER)) != len(FOUNDATIONAL_ORDER):
        raise AssertionError("FOUNDATIONAL_ORDER contains a duplicate topic")
    missing = set(TOPICS) - set(FOUNDATIONAL_ORDER)
    unknown = set(FOUNDATIONAL_ORDER) - set(TOPICS)
    if missing or unknown:
        raise AssertionError(
            "FOUNDATIONAL_ORDER must be a permutation of TOPICS (ADR-0070 section 7.1); "
            f"missing from the ordering: {sorted(missing)}; not in the vocabulary: {sorted(unknown)}"
        )


_verify_permutation()

# Position lookup, built once. Lower is earlier, and therefore preferred for a
# topic with insufficient history.
_POSITION: dict[str, int] = {topic: index for index, topic in enumerate(FOUNDATIONAL_ORDER)}


def foundational_position(topic: str) -> int:
    """Where `topic` sits in the foundational ordering. Lower comes first.

    Raises for an unknown topic rather than returning a sentinel: a topic outside
    the vocabulary means the caller has drifted from `TOPICS`, and ranking it
    last would hide that rather than surface it.
    """
    try:
        return _POSITION[topic]
    except KeyError:
        raise KeyError(f"{topic!r} is not in the topic vocabulary") from None
