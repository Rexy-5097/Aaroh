"""Aaroh's V1 DSA catalogue (ADR-0069).

Twelve hand-authored problems. This is the real catalogue the recommendation
endpoint serves, promoted deliberately from the ranking slice's test fixture so
there is exactly one definition rather than a production copy that can drift
from a tested one.

**It is explicitly UNVERSIONED, and that is a stated limitation.**

`ADR-0069` section 9 says a real catalogue should be a versioned artifact carrying
an immutable label and a SHA-256 digest -- but `ADR-0068` section 8 deliberately
deferred the *label format*, and inventing one here would fabricate exactly what
that ADR deferred. So V1 ships the catalogue as plain validated data with no
label, no digest and no trace linkage. The consequence is real and worth naming:
**a recommendation produced today cannot later be attributed to a specific
catalogue version.** That is acceptable while nothing is persisted, and must be
resolved before any recommendation is stored (`ADR-0072` D3, D6).

Why it lives in `domain/`
-------------------------
It is pure product data, the same kind as `TOPICS` and `FOUNDATIONAL_ORDER`, and
placing it here means the domain purity check covers it: the catalogue can never
acquire a database, HTTP or network import without CI failing.

Contents obey `ADR-0069`: immutable slug, title, one or more approved topics,
and an authored difficulty. **No estimated time** -- section 10 rejected invented
per-item durations. No platform identity, no company tags, no descriptions.
"""

from __future__ import annotations

from app.domain.catalogue import validate_item

# Chosen for coverage of the ranking rules rather than for breadth: several
# topics appear more than once so tie-breaks are exercised, two items carry
# multiple topics so the most-urgent rule has something to resolve, and the
# spread reaches across the foundational ordering rather than clustering at its
# start.
#
# Validated at import: an entry with an unknown topic, a bad difficulty or a
# malformed slug fails on load rather than at request time.
V1_CATALOGUE = tuple(
    validate_item(slug=slug, title=title, topics=topics, difficulty=difficulty)
    for slug, title, topics, difficulty in (
        ("two-sum", "Two Sum", ("arrays", "hash-tables"), "easy"),
        ("valid-anagram", "Valid Anagram", ("strings",), "easy"),
        ("group-anagrams", "Group Anagrams", ("strings", "hash-tables"), "medium"),
        ("container-with-most-water", "Container With Most Water", ("two-pointers",), "medium"),
        ("longest-substring", "Longest Substring Without Repeating Characters",
         ("sliding-window",), "medium"),
        ("merge-intervals", "Merge Intervals", ("sorting",), "medium"),
        ("binary-search", "Binary Search", ("binary-search",), "easy"),
        ("reverse-linked-list", "Reverse Linked List", ("linked-lists",), "easy"),
        ("valid-parentheses", "Valid Parentheses", ("stacks-and-queues",), "easy"),
        ("invert-binary-tree", "Invert Binary Tree", ("trees",), "easy"),
        ("course-schedule", "Course Schedule", ("graphs",), "medium"),
        ("climbing-stairs", "Climbing Stairs", ("dynamic-programming",), "easy"),
    )
)
