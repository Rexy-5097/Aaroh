"""DSA activity domain rules (ADR-0066).

Pure: no I/O, no framework, no clock. The controlled vocabularies live here
rather than in PostgreSQL so extending them is a code change with a test, not a
migration and a type alteration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_TITLE_LENGTH = 200
MAX_PLATFORM_LENGTH = 60
MIN_MINUTES = 1
# Beyond ten hours the record describes a study session, not one problem --
# and the session model is deliberately out of scope (ADR-0066 section 8).
MAX_MINUTES = 600

# Aaroh's controlled topic vocabulary (ADR-0066 section 4).
#
# Broad on purpose. A finer taxonomy (monotonic-stack, union-find) would be more
# precise and would churn as opinion shifts; these are the level at which
# students and interview material actually agree.
#
# Extending this is a one-line change plus a test. Order is presentation order.
TOPICS: tuple[str, ...] = (
    "arrays",
    "strings",
    "hash-tables",
    "two-pointers",
    "sliding-window",
    "stacks-and-queues",
    "linked-lists",
    "trees",
    "graphs",
    "heaps",
    "binary-search",
    "sorting",
    "recursion-and-backtracking",
    "dynamic-programming",
    "greedy",
    "math-and-bit-manipulation",
)

# Aaroh's own scale, not a platform's. A "medium" the student found hard is a
# genuine signal, and importing a platform's calibration would erase it.
DIFFICULTIES: tuple[str, ...] = ("easy", "medium", "hard")

# What happened. Self-reported: under manual entry there is nothing to verify
# against, and pretending otherwise would be fabricated rigour.
OUTCOMES: tuple[str, ...] = ("solved", "attempted")

_WHITESPACE = re.compile(r"\s+")


class InvalidActivity(ValueError):
    """A DSA activity that cannot be recorded.

    Ordinary input validation, so naming the field is helpful -- it discloses
    nothing about any other student, unlike an authentication failure.
    """

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class DsaActivity:
    """A validated practice event. Constructing one is the proof it is usable."""

    problem_title: str
    problem_ref: str
    topic: str
    difficulty: str
    outcome: str
    minutes_spent: int | None
    platform: str | None


def normalise_problem_ref(title: str) -> str:
    """Platform-independent identity of the underlying problem.

    Lowercase and whitespace only. Deliberately weak: a stronger normaliser
    (stemming, fuzzy matching, synonyms) would silently merge genuinely
    different problems, and merging is unrecoverable while splitting is not.
    """
    return _WHITESPACE.sub(" ", title.strip()).lower()


def _require_text(value: str | None, *, field: str, max_length: int) -> str:
    if value is None or not isinstance(value, str) or not value.strip():
        raise InvalidActivity(field, f"{field} is required")
    cleaned = _WHITESPACE.sub(" ", value.strip())
    if len(cleaned) > max_length:
        raise InvalidActivity(field, f"{field} must be at most {max_length} characters")
    return cleaned


def _require_member(value: str | None, allowed: tuple[str, ...], *, field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise InvalidActivity(
            field, f"{field} must be one of: {', '.join(allowed)}"
        )
    return value


def validate_activity(
    *,
    problem_title: str | None,
    topic: str | None,
    difficulty: str | None,
    outcome: str | None,
    minutes_spent: int | None = None,
    platform: str | None = None,
) -> DsaActivity:
    """Validate a practice event, or refuse it with the offending field named."""
    title = _require_text(problem_title, field="problem_title", max_length=MAX_TITLE_LENGTH)

    # Membership is exact and case-sensitive. Accepting "Arrays" or "ARRAYS"
    # would mean the vocabulary has variants, which is how a controlled list
    # quietly becomes free text.
    topic_value = _require_member(topic, TOPICS, field="topic")
    difficulty_value = _require_member(difficulty, DIFFICULTIES, field="difficulty")
    outcome_value = _require_member(outcome, OUTCOMES, field="outcome")

    if minutes_spent is not None:
        # bool is an int subclass, so `minutes_spent=True` would otherwise be
        # silently accepted as one minute.
        if isinstance(minutes_spent, bool) or not isinstance(minutes_spent, int):
            raise InvalidActivity("minutes_spent", "minutes_spent must be a whole number")
        if not MIN_MINUTES <= minutes_spent <= MAX_MINUTES:
            raise InvalidActivity(
                "minutes_spent",
                f"minutes_spent must be between {MIN_MINUTES} and {MAX_MINUTES}",
            )

    platform_value = None
    if platform is not None and str(platform).strip():
        platform_value = _require_text(
            platform, field="platform", max_length=MAX_PLATFORM_LENGTH
        )

    return DsaActivity(
        problem_title=title,
        problem_ref=normalise_problem_ref(title),
        topic=topic_value,
        difficulty=difficulty_value,
        outcome=outcome_value,
        minutes_spent=minutes_spent,
        platform=platform_value,
    )
