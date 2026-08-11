"""Golden tests for the V1 ranking engine (ADR-0071, ADR-0072).

Pure: no database, no HTTP, no clock. Every expected ordering below names the
product decision that produces it, because an expected ordering nobody can
justify is a guess with a test around it.

The decisions under test:
  ADR-0070 s6  foundational ordering for insufficiently observed topics
  ADR-0071 s3  lower solve rate = weaker; ordinal, no magnitude
  ADR-0071 s4  a topic needs >= 3 recorded activities to rank on history
  ADR-0072 B1  repair-first: demonstrated weakness outranks foundational
  ADR-0072 B2  slug ascending is the neutral tie-break
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.decision_engine import ReasonCode, rank
from app.decision_engine.ranking import EVIDENCE_THRESHOLD, RankingPreconditionError
from app.domain.catalogue import InvalidCatalogueItem, validate_item
from app.domain.foundational import FOUNDATIONAL_ORDER, foundational_position
from app.domain.goals import validate_goal
from app.domain.snapshot import snapshot_from_activities
from catalogue_fixture import CATALOGUE

SUBJECT = UUID("11111111-1111-4111-8111-111111111111")
NOON = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)

GOAL = validate_goal(
    target_role="Backend SWE",
    target_company=None,
    deadline=date(2026, 12, 1),
    weekly_hours=10,
    today=date(2026, 8, 12),
)


def activities(*specs):
    """(topic, solved_count, attempted_count) -> flat activity records."""
    out = []
    for topic, solved, attempted in specs:
        for _ in range(solved):
            out.append(_activity(topic, "solved"))
        for _ in range(attempted):
            out.append(_activity(topic, "attempted"))
    return out


def _activity(topic: str, outcome: str) -> dict:
    return {
        "topic": topic, "difficulty": "medium", "outcome": outcome,
        "minutes_spent": None, "occurred_at": NOON - timedelta(days=1),
    }


def ranked(*specs, catalog=CATALOGUE, goal=GOAL):
    snapshot = snapshot_from_activities(
        subject=SUBJECT, as_of=NOON, activities=activities(*specs))
    return rank(snapshot, goal, catalog)


def slugs(result) -> list[str]:
    return [c.slug for c in result.candidates]


def by_slug(result, slug):
    (candidate,) = [c for c in result.candidates if c.slug == slug]
    return candidate


# ── 1. Completely cold student ───────────────────────────────────────────────

def test_a_cold_student_is_ranked_by_the_foundational_ordering():
    """ADR-0070 s5: with no history every signal ties, so the foundational
    ordering decides. Every candidate is reasoned `foundational`."""
    result = ranked()
    assert len(result.candidates) == len(CATALOGUE)
    assert {c.reason for c in result.candidates} == {ReasonCode.FOUNDATIONAL}

    positions = [foundational_position(c.reason_topic) for c in result.candidates]
    assert positions == sorted(positions), "cold ordering must follow FOUNDATIONAL_ORDER"


def test_the_cold_winner_is_the_earliest_foundational_topic_present():
    """`arrays` is foundational position 1 and `two-sum` is the only candidate
    carrying it, so it must lead."""
    result = ranked()
    assert result.candidates[0].slug == "two-sum"
    assert result.candidates[0].reason_topic == "arrays"
    assert result.candidates[0].position == 1


# ── 2-3. The evidence boundary (ADR-0071 s4) ─────────────────────────────────

def test_two_activities_is_not_enough_evidence():
    """Below the threshold the topic stays foundational, however bad it looks.
    `graphs` with 0 solves in 2 attempts is still insufficiently observed."""
    result = ranked(("graphs", 0, 2))
    assert by_slug(result, "course-schedule").reason == ReasonCode.FOUNDATIONAL
    assert result.candidates[0].slug == "two-sum", "a cold ordering is unchanged"


def test_exactly_three_activities_crosses_the_threshold():
    """ADR-0071 s4 makes 3 the boundary, and `graphs` at 0/3 is maximally weak,
    so repair-first (ADR-0072 B1) puts it first."""
    result = ranked(("graphs", 0, 3))
    winner = result.candidates[0]
    assert winner.slug == "course-schedule"
    assert winner.reason == ReasonCode.WEAK_TOPIC
    assert winner.reason_topic == "graphs"


def test_the_threshold_constant_matches_the_adr():
    assert EVIDENCE_THRESHOLD == 3


@pytest.mark.parametrize("solved,attempted,eligible", [
    (0, 2, False), (1, 1, False), (2, 0, False),
    (0, 3, True), (1, 2, True), (3, 0, True),
])
def test_the_threshold_counts_solved_and_attempted_together(solved, attempted, eligible):
    """ADR-0071 s3: `solved` and `attempted` are DISJOINT counts, so the total is
    their sum. A student who only ever solves must still become eligible --
    counting `attempted` alone would leave them permanently unranked."""
    result = ranked(("graphs", solved, attempted))
    expected = ReasonCode.WEAK_TOPIC if eligible else ReasonCode.FOUNDATIONAL
    assert by_slug(result, "course-schedule").reason == expected


# ── 4-6. Solve rate orders the repair tier (ADR-0071 s3) ─────────────────────

def test_zero_solves_ranks_above_one_solve():
    """0/3 is a lower solve rate than 1/3, so `graphs` precedes `trees`."""
    result = ranked(("graphs", 0, 3), ("trees", 1, 2))
    assert slugs(result)[:2] == ["course-schedule", "invert-binary-tree"]


def test_a_fully_solved_topic_is_the_weakest_no_longer():
    """3/3 is the highest possible solve rate, so `trees` sits last within the
    repair tier -- but still ahead of every foundational candidate (B1)."""
    result = ranked(("graphs", 0, 3), ("trees", 3, 0))
    order = slugs(result)
    assert order[0] == "course-schedule"
    assert order[1] == "invert-binary-tree", "a solved-heavy topic is still repair-tier"
    assert order[2:] and by_slug(result, order[2]).reason == ReasonCode.FOUNDATIONAL


def test_solve_rate_not_raw_counts_decides():
    """1/4 (25%) is weaker than 3/6 (50%) even though it has fewer attempts --
    the model is a rate, not a deficit count."""
    result = ranked(("graphs", 1, 3), ("trees", 3, 3))
    assert slugs(result)[:2] == ["course-schedule", "invert-binary-tree"]


# ── 7-8. Repair-first (ADR-0072 B1) ──────────────────────────────────────────

def test_demonstrated_weakness_outranks_an_untouched_foundational_topic():
    """THE B1 DECISION. `graphs` is foundational position 13 -- nearly last --
    yet 1/4 of demonstrated weakness puts it ahead of `arrays` at position 1."""
    result = ranked(("graphs", 1, 3))
    assert result.candidates[0].slug == "course-schedule"
    assert result.candidates[0].reason == ReasonCode.WEAK_TOPIC
    assert by_slug(result, "two-sum").reason == ReasonCode.FOUNDATIONAL


def test_every_repair_candidate_precedes_every_foundational_one():
    """The tiers do not interleave (B1)."""
    result = ranked(("graphs", 1, 3), ("dynamic-programming", 0, 3))
    reasons = [c.reason for c in result.candidates]
    first_foundational = reasons.index(ReasonCode.FOUNDATIONAL)
    assert ReasonCode.WEAK_TOPIC not in reasons[first_foundational:]


def test_multiple_weak_topics_order_among_themselves_by_rate():
    result = ranked(("graphs", 2, 2), ("trees", 0, 3), ("sorting", 1, 3))
    assert slugs(result)[:3] == ["invert-binary-tree", "merge-intervals", "course-schedule"]


# ── 9-10. Ties (ADR-0072 B2) ─────────────────────────────────────────────────

def test_equal_solve_rates_fall_through_to_the_foundational_ordering():
    """Both 1/3. The repair tier is indifferent, so the declared foundational
    ordering decides -- `sorting` (6) before `graphs` (13)."""
    result = ranked(("graphs", 1, 2), ("sorting", 1, 2))
    assert slugs(result)[:2] == ["merge-intervals", "course-schedule"]


def test_candidates_sharing_a_topic_break_ties_by_slug():
    """`group-anagrams` and `valid-anagram` are both `strings`, identically
    placed. Slug ascending is a neutral tie-break: it introduces no learning
    preference (B2)."""
    result = ranked(("strings", 1, 3))
    order = [s for s in slugs(result) if s in {"group-anagrams", "valid-anagram"}]
    assert order == ["group-anagrams", "valid-anagram"]


def test_the_tie_break_is_slug_not_title():
    """Discriminating case: these two share a topic and are otherwise identical,
    and their slug order is the REVERSE of their title order. A tie-break on
    title would flip them. Slug is the declared neutral rule (ADR-0072 B2)."""
    pair = (
        validate_item(slug="aardvark-problem", title="Zebra Traversal",
                      topics=("greedy",), difficulty="easy"),
        validate_item(slug="zebra-problem", title="Aardvark Traversal",
                      topics=("greedy",), difficulty="easy"),
    )
    result = ranked(("greedy", 1, 3), catalog=pair)
    assert slugs(result) == ["aardvark-problem", "zebra-problem"]


def test_every_candidate_is_ranked_and_none_is_dropped():
    """The result is a permutation of the catalogue. The snapshot is dense over
    all 16 topics (ADR-0067 s4.1), so no candidate can be lost to a missing
    topic -- this asserts that rather than assuming it."""
    for specs in ([], [("graphs", 1, 3)], [("arrays", 0, 5), ("trees", 3, 1)]):
        result = ranked(*specs)
        assert sorted(slugs(result)) == sorted(i.slug for i in CATALOGUE)
        assert len(result.candidates) == len(CATALOGUE)


def test_all_candidates_tied_still_yields_a_total_order():
    """A cold student ties every signal; the result must still be a stable,
    complete permutation with no duplicate positions."""
    result = ranked()
    assert [c.position for c in result.candidates] == list(range(1, len(CATALOGUE) + 1))
    assert len(set(slugs(result))) == len(CATALOGUE)


# ── 11-12. Determinism (ADR-0059) ────────────────────────────────────────────

def test_repeated_execution_is_identical():
    a, b = ranked(("graphs", 1, 3)), ranked(("graphs", 1, 3))
    assert a == b and slugs(a) == slugs(b)


def test_catalogue_input_order_does_not_affect_the_result():
    """Ordering must come from the model, not from how the catalogue was typed
    (ADR-0069 s16)."""
    forward = ranked(("graphs", 1, 3), catalog=CATALOGUE)
    reversed_ = ranked(("graphs", 1, 3), catalog=tuple(reversed(CATALOGUE)))
    assert slugs(forward) == slugs(reversed_)


def test_topic_tag_order_does_not_affect_the_result():
    """ADR-0069 s6: a candidate's topics are an unordered set."""
    swapped = tuple(
        validate_item(slug=i.slug, title=i.title, topics=tuple(reversed(i.topics)),
                      difficulty=i.difficulty)
        for i in CATALOGUE
    )
    assert slugs(ranked(("hash-tables", 1, 3), catalog=CATALOGUE)) == \
           slugs(ranked(("hash-tables", 1, 3), catalog=swapped))


def test_the_result_is_immutable():
    result = ranked()
    with pytest.raises(Exception):
        result.candidates[0].position = 99  # type: ignore[misc]
    assert isinstance(result.candidates, tuple)


# ── Multi-topic candidates (ADR-0072 B3) ─────────────────────────────────────

def test_a_candidate_is_placed_by_its_most_urgent_topic():
    """`two-sum` is (arrays, hash-tables). With `hash-tables` demonstrably weak
    and `arrays` untouched, repair-first requires the weak topic to decide --
    demoting it for also touching an untouched topic would contradict B1."""
    result = ranked(("hash-tables", 0, 3))
    winner = result.candidates[0]
    assert winner.slug in {"two-sum", "group-anagrams"}
    assert winner.reason == ReasonCode.WEAK_TOPIC
    assert winner.reason_topic == "hash-tables"


# ── No fabricated model (ADR-0060, ADR-0071) ─────────────────────────────────

def test_weights_cannot_change_the_v1_ordering():
    """Proves mechanically that no coefficient has crept in. V1 reads no value
    from `weights`; if this ever fails, a hidden weight exists."""
    snapshot = snapshot_from_activities(
        subject=SUBJECT, as_of=NOON, activities=activities(("graphs", 1, 3)))
    baseline = rank(snapshot, GOAL, CATALOGUE, None)
    for weights in ({}, {"topic_weight": 99}, [1, 2, 3], "anything"):
        assert rank(snapshot, GOAL, CATALOGUE, weights) == baseline


def test_the_result_exposes_no_score_or_confidence():
    """ADR-0071 s3.1 made weakness ordinal with no magnitude, so there is no
    score to expose; confidence is undefined everywhere."""
    import dataclasses

    from app.decision_engine.ranking import RankedCandidate

    names = {f.name for f in dataclasses.fields(RankedCandidate)}
    assert names == {"slug", "position", "reason", "reason_topic"}
    for forbidden in ("score", "confidence", "weight", "rating", "percent"):
        assert not any(forbidden in n for n in names)


def test_reason_codes_are_a_closed_two_value_vocabulary():
    assert set(ReasonCode.ALL) == {"weak-topic", "foundational"}
    result = ranked(("graphs", 1, 3))
    assert {c.reason for c in result.candidates} <= set(ReasonCode.ALL)


def test_no_floating_point_appears_in_the_engine():
    """Solve rates are compared by integer cross-multiplication, so
    cross-platform float behaviour cannot alter an ordering."""
    import ast
    import importlib
    import inspect

    # importlib, not `from app.decision_engine import ranking`: the package
    # re-exports a function, and an attribute lookup that returns a function
    # would make this test inspect one function instead of the whole file.
    module = importlib.import_module("app.decision_engine.ranking")
    source = inspect.getsource(module)
    assert "def _weaker_than" in source, "the whole module must be under inspection"
    tree = ast.parse(source)
    floats = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
    assert not floats, "a float literal appeared in the ranking engine"
    divisions = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)]
    assert not divisions, "true division appeared; use integer cross-multiplication"


def test_large_counts_cannot_overflow_the_comparison():
    """Python integers are arbitrary precision, so cross-multiplication is exact
    at any scale a student could reach."""
    result = ranked(("graphs", 1, 10**6), ("trees", 2, 10**6))
    assert slugs(result)[:2] == ["course-schedule", "invert-binary-tree"]


# ── Preconditions (ADR-0065) ─────────────────────────────────────────────────

def test_ranking_without_a_preparation_goal_is_refused():
    """ADR-0065's product rule, enforced as a refusal rather than a score."""
    snapshot = snapshot_from_activities(subject=SUBJECT, as_of=NOON, activities=[])
    with pytest.raises(RankingPreconditionError):
        rank(snapshot, None, CATALOGUE)  # type: ignore[arg-type]


def test_ranking_requires_a_real_snapshot():
    with pytest.raises(RankingPreconditionError):
        rank({"dsa": None}, GOAL, CATALOGUE)  # type: ignore[arg-type]


# ── Catalogue validation (ADR-0069) ──────────────────────────────────────────

def test_the_fixture_catalogue_is_valid_and_has_twelve_problems():
    assert len(CATALOGUE) == 12
    assert len({i.slug for i in CATALOGUE}) == 12


@pytest.mark.parametrize("bad,field", [
    ({"topics": ()}, "topics"),
    ({"topics": ("monotonic-stack",)}, "topics"),
    ({"topics": ("arrays", "arrays")}, "topics"),
    ({"difficulty": "trivial"}, "difficulty"),
    ({"slug": "Two Sum"}, "slug"),
    ({"slug": "-leading"}, "slug"),
    ({"slug": ""}, "slug"),
    ({"title": "  "}, "title"),
])
def test_invalid_catalogue_items_are_refused_with_the_field_named(bad, field):
    args = {"slug": "ok-slug", "title": "Ok", "topics": ("arrays",), "difficulty": "easy"}
    args.update(bad)
    with pytest.raises(InvalidCatalogueItem) as exc:
        validate_item(**args)
    assert exc.value.field == field


def test_duplicate_slugs_are_refused():
    """Slug uniqueness is what makes the tie-break total."""
    from app.domain.catalogue import validate_catalogue

    item = validate_item(slug="dup", title="A", topics=("arrays",), difficulty="easy")
    with pytest.raises(InvalidCatalogueItem) as exc:
        validate_catalogue([item, item])
    assert exc.value.field == "slug"


def test_the_catalogue_carries_no_duration_field():
    """ADR-0069 s10 rejected invented per-item time."""
    import dataclasses

    from app.domain.catalogue import CatalogueItem

    names = {f.name for f in dataclasses.fields(CatalogueItem)}
    for forbidden in ("minutes", "duration", "estimated", "time"):
        assert not any(forbidden in n for n in names)


# ── The foundational ordering (ADR-0070) ─────────────────────────────────────

def test_the_foundational_ordering_is_a_permutation_of_the_vocabulary():
    """ADR-0070 s7.1's invariant: a topic added to TOPICS but not here would be
    silently ignored at cold start."""
    from app.domain.dsa import TOPICS

    assert sorted(FOUNDATIONAL_ORDER) == sorted(TOPICS)
    assert len(set(FOUNDATIONAL_ORDER)) == len(FOUNDATIONAL_ORDER)


def test_the_foundational_ordering_is_not_the_presentation_ordering():
    """ADR-0070 s7: the two are independent and mean different things."""
    from app.domain.dsa import TOPICS

    assert FOUNDATIONAL_ORDER != TOPICS
    assert FOUNDATIONAL_ORDER[0] == "arrays"


def test_an_unknown_topic_has_no_foundational_position():
    with pytest.raises(KeyError):
        foundational_position("monotonic-stack")
