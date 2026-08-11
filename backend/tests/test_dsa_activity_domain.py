"""DSA activity domain rules (ADR-0066).

Pure unit tests — no database, no HTTP. The controlled vocabularies live in the
domain layer, so this is where their membership is proven.
"""

from __future__ import annotations

import pytest

from app.domain.dsa import (
    DIFFICULTIES,
    MAX_MINUTES,
    MAX_PLATFORM_LENGTH,
    MAX_TITLE_LENGTH,
    MIN_MINUTES,
    OUTCOMES,
    TOPICS,
    DsaActivity,
    InvalidActivity,
    normalise_problem_ref,
    validate_activity,
)


def build(**overrides):
    args = dict(
        problem_title="Two Sum",
        topic="arrays",
        difficulty="easy",
        outcome="solved",
        minutes_spent=None,
        platform=None,
    )
    args.update(overrides)
    return validate_activity(**args)


# ── Accepted ─────────────────────────────────────────────────────────────────

def test_a_minimal_activity_is_accepted():
    activity = build()
    assert isinstance(activity, DsaActivity)
    assert activity.problem_title == "Two Sum"
    assert activity.minutes_spent is None
    assert activity.platform is None


def test_a_complete_activity_is_accepted():
    activity = build(minutes_spent=25, platform="LeetCode", topic="graphs",
                     difficulty="hard", outcome="attempted")
    assert (activity.topic, activity.difficulty, activity.outcome) == (
        "graphs", "hard", "attempted")
    assert activity.minutes_spent == 25
    assert activity.platform == "LeetCode"


def test_the_activity_is_immutable():
    with pytest.raises(Exception):
        build().topic = "graphs"  # type: ignore[misc]


# ── Topic vocabulary ─────────────────────────────────────────────────────────

def test_there_are_sixteen_topics():
    assert len(TOPICS) == 16
    assert len(set(TOPICS)) == 16, "the vocabulary contains a duplicate"


@pytest.mark.parametrize("topic", TOPICS)
def test_every_declared_topic_is_accepted(topic):
    assert build(topic=topic).topic == topic


@pytest.mark.parametrize(
    "topic",
    ["", "  ", None, "unknown", "Arrays", "ARRAYS", "dynamic programming",
     "monotonic-stack", "arrays;drop", 42],
)
def test_unknown_topics_are_rejected(topic):
    """Membership is exact and case-sensitive: accepting `Arrays` would mean the
    vocabulary has variants, which is how a controlled list becomes free text."""
    with pytest.raises(InvalidActivity) as exc:
        build(topic=topic)
    assert exc.value.field == "topic"


def test_topics_are_lowercase_kebab_slugs():
    for topic in TOPICS:
        assert topic == topic.lower()
        assert " " not in topic
        assert "_" not in topic


# ── Difficulty ───────────────────────────────────────────────────────────────

def test_difficulty_vocabulary_is_exactly_three_values():
    assert DIFFICULTIES == ("easy", "medium", "hard")


@pytest.mark.parametrize("difficulty", DIFFICULTIES)
def test_every_difficulty_is_accepted(difficulty):
    assert build(difficulty=difficulty).difficulty == difficulty


@pytest.mark.parametrize(
    "difficulty", ["", None, "Easy", "EASY", "trivial", "very-hard", "impossible", 1]
)
def test_unknown_difficulties_are_rejected(difficulty):
    with pytest.raises(InvalidActivity) as exc:
        build(difficulty=difficulty)
    assert exc.value.field == "difficulty"


# ── Outcome ──────────────────────────────────────────────────────────────────

def test_outcome_vocabulary_is_exactly_two_values():
    assert OUTCOMES == ("solved", "attempted")


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_every_outcome_is_accepted(outcome):
    assert build(outcome=outcome).outcome == outcome


@pytest.mark.parametrize(
    "outcome", ["", None, "Solved", "skipped", "reviewed", "partial", True]
)
def test_unknown_outcomes_are_rejected(outcome):
    with pytest.raises(InvalidActivity) as exc:
        build(outcome=outcome)
    assert exc.value.field == "outcome"


# ── Problem identity and normalisation ───────────────────────────────────────

@pytest.mark.parametrize(
    "title,expected",
    [
        ("Two Sum", "two sum"),
        ("  Two Sum  ", "two sum"),
        ("Two   Sum", "two sum"),
        ("TWO SUM", "two sum"),
        ("tWo\tSum", "two sum"),
        ("Two\nSum", "two sum"),
    ],
)
def test_problem_ref_normalisation(title, expected):
    """Case and whitespace only. Deliberately weak: a stronger normaliser would
    silently merge genuinely different problems, and merging is unrecoverable."""
    assert normalise_problem_ref(title) == expected
    assert build(problem_title=title).problem_ref == expected


def test_differently_typed_titles_share_one_problem_ref():
    a = build(problem_title="Longest Substring")
    b = build(problem_title="  longest   SUBSTRING ")
    assert a.problem_ref == b.problem_ref
    assert a.problem_title != b.problem_title, "the typed title is preserved separately"


def test_normalisation_does_not_merge_different_problems():
    assert build(problem_title="Two Sum").problem_ref != build(
        problem_title="Three Sum").problem_ref
    assert build(problem_title="Add Two Numbers").problem_ref != build(
        problem_title="Add Two Number").problem_ref, "no stemming, by design"


@pytest.mark.parametrize("title", ["", "   ", "\t\n", None, 42])
def test_empty_problem_titles_are_rejected(title):
    with pytest.raises(InvalidActivity) as exc:
        build(problem_title=title)
    assert exc.value.field == "problem_title"


def test_problem_title_length_boundary():
    assert build(problem_title="x" * MAX_TITLE_LENGTH) is not None
    with pytest.raises(InvalidActivity) as exc:
        build(problem_title="x" * (MAX_TITLE_LENGTH + 1))
    assert exc.value.field == "problem_title"


# ── minutes_spent ────────────────────────────────────────────────────────────

def test_minutes_spent_is_optional():
    assert build(minutes_spent=None).minutes_spent is None


@pytest.mark.parametrize("minutes", [MIN_MINUTES, 30, MAX_MINUTES])
def test_minutes_within_range_are_accepted(minutes):
    assert build(minutes_spent=minutes).minutes_spent == minutes


@pytest.mark.parametrize("minutes", [0, -1, MAX_MINUTES + 1, 10_000])
def test_minutes_outside_range_are_rejected(minutes):
    with pytest.raises(InvalidActivity) as exc:
        build(minutes_spent=minutes)
    assert exc.value.field == "minutes_spent"


@pytest.mark.parametrize("minutes", ["30", 30.5, True, False])
def test_non_integer_minutes_are_rejected(minutes):
    """`True`/`False` included deliberately: bool is an int subclass, so
    `minutes_spent=True` would otherwise be accepted as one minute."""
    with pytest.raises(InvalidActivity) as exc:
        build(minutes_spent=minutes)
    assert exc.value.field == "minutes_spent"


# ── platform ─────────────────────────────────────────────────────────────────

def test_platform_is_optional_and_blank_means_absent():
    assert build(platform=None).platform is None
    assert build(platform="   ").platform is None


def test_any_platform_name_is_accepted():
    """No allow-list: constraining it would be a decision about which platforms
    Aaroh endorses, and no such decision exists."""
    for name in ("LeetCode", "Codeforces", "a whiteboard", "pen and paper"):
        assert build(platform=name).platform == name


def test_platform_length_boundary():
    assert build(platform="p" * MAX_PLATFORM_LENGTH) is not None
    with pytest.raises(InvalidActivity) as exc:
        build(platform="p" * (MAX_PLATFORM_LENGTH + 1))
    assert exc.value.field == "platform"


def test_validation_reports_the_offending_field():
    with pytest.raises(InvalidActivity) as exc:
        build(topic="nope")
    assert exc.value.field == "topic"
    assert "topic" in exc.value.message
