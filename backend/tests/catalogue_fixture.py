"""A small hand-authored DSA catalogue for the ranking tests (ADR-0069).

Twelve problems. Deliberately a **test fixture, not a production artifact**:
`ADR-0069` section 9 says a real catalogue is a versioned file carrying an
immutable label and a SHA-256 digest, and `ADR-0068` section 8 explicitly
deferred the *label format*. Authoring a versioned artifact before its
identifier format exists would invent the thing that ADR deferred.

The engine takes `catalog` as an explicit input, so it needs no production
catalogue to be proven correct -- only real data of the right shape.

Titles are the ordinary names of well-known problems. No durations: `ADR-0069`
section 10 rejected invented per-item time, and none appears here.
"""

from __future__ import annotations

from app.domain.catalogue import validate_item

# Chosen for coverage rather than realism: several topics appear more than once
# so tie-breaks are exercised, and one item is multi-topic so the most-urgent
# rule has something to resolve.
CATALOGUE = tuple(
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
