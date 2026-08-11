"""V1 ranking: repair-first, ordinal topic weakness (ADR-0071, ADR-0072).

    rank(snapshot, constraints, catalog, weights) -> RankedResult

Pure. Every input is explicit; the same inputs produce the same output, in the
same order, in every process (`ADR-0059`).

The model in four sentences
---------------------------
A candidate is placed by its **most urgent topic**. A topic with at least three
recorded activities is *history-eligible* and ranks by solve rate, lower first.
A topic below that threshold is *insufficiently observed* and ranks by the
foundational ordering. Repair beats foundation: any history-eligible candidate
outranks every insufficiently observed one (`ADR-0072` B1).

What is deliberately absent
---------------------------
No score. `ADR-0071` section 3.1 made weakness **ordinal with no magnitude** --
Aaroh may say "graphs is weaker than trees" and must not say "twice as weak" --
so there is no number to return and none is invented.

No coefficients, no difficulty multiplier, no time multiplier, no recency decay,
no confidence, no exploration bonus. `weights` is accepted because the contract
carries it (`ADR-0060`), and V1 reads no value from it; a test asserts that
changing it cannot change the output.

No floating point. Solve rates are compared by integer cross-multiplication
(section `_weaker_than`), so cross-platform float behaviour cannot alter an
ordering. Python integers are arbitrary precision, so the products cannot
overflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.catalogue import CatalogueItem, validate_catalogue
from app.domain.foundational import foundational_position
from app.domain.goals import PreparationGoal
from app.domain.snapshot import StudentSnapshot, TopicStat

# ADR-0071 section 4. A topic needs at least this many recorded activities
# (solved + attempted) before its history is used. Below it, the foundational
# ordering applies. The value is a product decision dated 2026-08-12, with the
# honest basis ADR-0060 requires: judgement, unvalidated.
EVIDENCE_THRESHOLD = 3


class ReasonCode:
    """Why a candidate holds its position.

    A closed vocabulary of exactly two values, and it is closed because the model
    has exactly two states (`ADR-0072` B3). It is not free text and not prose:
    `ADR-0059` places explanation downstream, template-first, after the engine.

    The codes exist because `README.md` treats a recommendation that cannot be
    explained as a **defect** -- the caller needs to know *which* rule placed a
    candidate in order to say why.
    """

    WEAK_TOPIC = "weak-topic"
    FOUNDATIONAL = "foundational"

    ALL = (WEAK_TOPIC, FOUNDATIONAL)


class RankingPreconditionError(ValueError):
    """The engine was asked to rank without the inputs the product requires.

    `ADR-0065`: "No recommendation may exist without a deadline and a time
    budget." That is a precondition on running at all, not a ranking factor
    (`ADR-0070` section 4), so it is enforced here as a refusal rather than
    folded into a score.
    """


@dataclass(frozen=True)
class RankedCandidate:
    """One placed candidate.

    Three fields plus the topic that explains it. No score (`ADR-0071` 3.1), no
    confidence (undefined anywhere), and no version strings -- the caller already
    holds those and a pure function restating its own inputs adds nothing
    (`ADR-0072` B3).
    """

    slug: str
    position: int
    reason: str
    reason_topic: str


@dataclass(frozen=True)
class RankedResult:
    """The full ordered candidate set.

    Every candidate, not just the winner. `ADR-0060`: "Storing only the winning
    task is insufficient -- the rejected candidates are what make the answer
    meaningful."
    """

    candidates: tuple[RankedCandidate, ...]


def _totals(stat: TopicStat) -> int:
    """Recorded activity in a topic.

    `solved` and `attempted` are **disjoint** counts -- `attempted` is an outcome
    value meaning "engaged with and not completed" (`ADR-0066`), not a try count.
    So the total is their sum, and the solve rate's denominator is this
    (`ADR-0071` section 3).
    """
    return stat.solved + stat.attempted


def _weaker_than(left: TopicStat, right: TopicStat) -> bool:
    """True when `left` has the lower solve rate, compared without floats.

    `left.solved / left_total < right.solved / right_total` is equivalent to
    `left.solved * right_total < right.solved * left_total` for positive totals.
    Both totals are positive here because only history-eligible topics reach this
    function.
    """
    return left.solved * _totals(right) < right.solved * _totals(left)


@dataclass(frozen=True)
class _Placement:
    """Internal sort key. Never returned; see `RankedCandidate`."""

    tier: int  # 0 = repair, 1 = foundational. ADR-0072 B1.
    topic: str
    stat: TopicStat | None  # present iff tier == 0
    foundational: int


def _placement_for(topic: str, stat: TopicStat | None) -> _Placement:
    if stat is not None and _totals(stat) >= EVIDENCE_THRESHOLD:
        return _Placement(tier=0, topic=topic, stat=stat, foundational=foundational_position(topic))
    return _Placement(tier=1, topic=topic, stat=None, foundational=foundational_position(topic))


def _more_urgent(left: _Placement, right: _Placement) -> bool:
    """True when `left` should be preferred over `right`.

    Repair before foundation (`ADR-0072` B1). Inside the repair tier, the weaker
    topic wins; a genuine tie there falls through to the foundational ordering,
    which is a *declared* preference rather than a hidden one.
    """
    if left.tier != right.tier:
        return left.tier < right.tier
    if left.tier == 0:
        assert left.stat is not None and right.stat is not None
        if _weaker_than(left.stat, right.stat):
            return True
        if _weaker_than(right.stat, left.stat):
            return False
    return left.foundational < right.foundational


def _candidate_placement(item: CatalogueItem, stats: dict[str, TopicStat]) -> _Placement:
    """The placement of an item's **most urgent** topic.

    A candidate may carry several topics and their order is not significant
    (`ADR-0069` section 6). Taking the most urgent one follows directly from
    repair-first: if a problem can address a demonstrated weakness, demoting it
    because it *also* touches an untouched topic would contradict `ADR-0072` B1.
    """
    best: _Placement | None = None
    for topic in item.topics:
        placement = _placement_for(topic, stats.get(topic))
        if best is None or _more_urgent(placement, best):
            best = placement
    assert best is not None  # validate_item guarantees at least one topic
    return best


def rank(
    snapshot: StudentSnapshot,
    constraints: PreparationGoal,
    catalog: Any,
    weights: Any = None,
) -> RankedResult:
    """Order every catalogue candidate for one student.

    `weights` is part of the contract (`ADR-0060`) and **V1 reads no value from
    it**. It is accepted so that adding the first weight set later needs no
    signature change, and `test_weights_cannot_change_the_v1_ordering` proves
    mechanically that no coefficient has crept in.
    """
    if not isinstance(snapshot, StudentSnapshot):
        raise RankingPreconditionError("snapshot must be a StudentSnapshot")
    if not isinstance(constraints, PreparationGoal):
        # ADR-0065's product rule, enforced as a refusal.
        raise RankingPreconditionError(
            "ranking requires a preparation goal: no recommendation may exist "
            "without a deadline and a weekly time budget"
        )

    items = validate_catalogue(catalog)
    stats = {stat.topic: stat for stat in snapshot.dsa.topics}

    placed = [(_candidate_placement(item, stats), item) for item in items]

    # Deterministic total order. The first three keys are product rules; `slug`
    # is the neutral tie-break (ADR-0072 B2) and makes the order total, since
    # validate_catalogue guarantees slugs are unique.
    placed.sort(
        key=lambda pair: (
            pair[0].tier,
            _SolveRateKey(pair[0].stat) if pair[0].stat is not None else _SolveRateKey(None),
            pair[0].foundational,
            pair[1].slug,
        )
    )

    return RankedResult(
        candidates=tuple(
            RankedCandidate(
                slug=item.slug,
                position=index + 1,
                reason=ReasonCode.WEAK_TOPIC if placement.tier == 0 else ReasonCode.FOUNDATIONAL,
                reason_topic=placement.topic,
            )
            for index, (placement, item) in enumerate(placed)
        )
    )


class _SolveRateKey:
    """Sort key comparing solve rates by integer cross-multiplication.

    A plain tuple key cannot express "compare a/b against c/d without floats", so
    the comparison is carried here. Foundational-tier entries carry no stat and
    all compare equal, letting the next sort key decide.
    """

    __slots__ = ("stat",)

    def __init__(self, stat: TopicStat | None) -> None:
        self.stat = stat

    def __lt__(self, other: _SolveRateKey) -> bool:
        if self.stat is None or other.stat is None:
            return False
        return _weaker_than(self.stat, other.stat)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _SolveRateKey):
            return NotImplemented
        if self.stat is None or other.stat is None:
            return self.stat is None and other.stat is None
        return not _weaker_than(self.stat, other.stat) and not _weaker_than(other.stat, self.stat)
