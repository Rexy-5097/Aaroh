"""DSA catalogue items (ADR-0069).

One item is one DSA problem Aaroh can recommend next -- *opportunity*, not
history. It is deliberately not a `dsa_activities` row, which records what a
student did (`ADR-0069` section 2).

Four required fields, and no more (`ADR-0069` section 4): `slug` identifies,
`title` is the only thing a student can be shown, `topics` is the sole join to
the snapshot, and `difficulty` is the only other dimension the snapshot carries.
Description, prerequisites, popularity and company tags were each considered and
refused -- none is needed to rank, and every one is a maintenance obligation on
hand-authored data.

Deliberately absent: **any duration**. `ADR-0069` section 10 rejected a per-item
`estimated_minutes` because how long a problem takes is a property of the
student, not the problem, and with no ingestion the number would be invented by
whoever wrote the entry.

Pure: no I/O, no clock, no framework. Governed by the domain purity check.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.dsa import DIFFICULTIES, TOPICS

MAX_SLUG_LENGTH = 100
MAX_TITLE_LENGTH = 200
MAX_PLATFORM_LENGTH = 60
MAX_REFERENCE_LENGTH = 300

_SLUG_ALPHABET = set("abcdefghijklmnopqrstuvwxyz0123456789-")


class InvalidCatalogueItem(ValueError):
    """An item that cannot be ranked.

    `field` lets a catalogue author see which entry is wrong. This is authoring
    feedback, not user-facing input validation, so being specific is free.
    """

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class ExternalReference:
    """Where this problem can be found. Metadata only.

    `ADR-0069` section 8 keeps three things apart: Aaroh's own identity (the
    slug), an external identity (this), and ingestion (not built). Recording
    that a problem exists somewhere creates no dependency; *calling* that
    platform would, and nothing here calls anything.
    """

    platform: str
    reference: str


@dataclass(frozen=True)
class CatalogueItem:
    """One recommendable DSA problem.

    `topics` is a tuple for immutability, but **order within it is not
    significant** (`ADR-0069` section 6). Treating position as primacy would
    smuggle a weight into the catalogue, so the engine must not read meaning
    into it.
    """

    slug: str
    title: str
    topics: tuple[str, ...]
    difficulty: str
    external_refs: tuple[ExternalReference, ...] = ()


def _clean_text(value: object, *, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidCatalogueItem(field, f"{field} is required")
    cleaned = value.strip()
    if len(cleaned) > limit:
        raise InvalidCatalogueItem(field, f"{field} must be at most {limit} characters")
    return cleaned


def validate_item(
    *,
    slug: object,
    title: object,
    topics: object,
    difficulty: object,
    external_refs: object = (),
) -> CatalogueItem:
    """Validate one catalogue entry, or refuse it with the offending field named."""
    slug_value = _clean_text(slug, field="slug", limit=MAX_SLUG_LENGTH)
    # Kebab-case only. ADR-0069 section 3 chose a human-readable slug precisely so
    # catalogue diffs and golden files stay reviewable; permitting arbitrary text
    # would let that erode one entry at a time.
    if set(slug_value) - _SLUG_ALPHABET or slug_value.startswith("-") or slug_value.endswith("-"):
        raise InvalidCatalogueItem(
            "slug", "slug must be lowercase kebab-case: a-z, 0-9 and interior hyphens"
        )

    title_value = _clean_text(title, field="title", limit=MAX_TITLE_LENGTH)

    if not isinstance(topics, (tuple, list)) or not topics:
        raise InvalidCatalogueItem("topics", "at least one topic is required")
    unknown = [t for t in topics if t not in TOPICS]
    if unknown:
        # ADR-0067 section 8: catalogue tags must come from the same TOPICS tuple,
        # or the join to the snapshot goes lossy in a way no test would catch.
        raise InvalidCatalogueItem("topics", f"topics outside the vocabulary: {unknown}")
    if len(set(topics)) != len(topics):
        raise InvalidCatalogueItem("topics", "a topic is repeated")

    if difficulty not in DIFFICULTIES:
        raise InvalidCatalogueItem("difficulty", f"difficulty must be one of {DIFFICULTIES}")

    refs: list[ExternalReference] = []
    for ref in external_refs or ():
        if isinstance(ref, ExternalReference):
            platform, reference = ref.platform, ref.reference
        elif isinstance(ref, (tuple, list)) and len(ref) == 2:
            platform, reference = ref
        else:
            raise InvalidCatalogueItem("external_refs", "each reference is (platform, reference)")
        refs.append(
            ExternalReference(
                platform=_clean_text(platform, field="external_refs", limit=MAX_PLATFORM_LENGTH),
                reference=_clean_text(reference, field="external_refs", limit=MAX_REFERENCE_LENGTH),
            )
        )

    return CatalogueItem(
        slug=slug_value,
        title=title_value,
        topics=tuple(topics),
        difficulty=str(difficulty),
        external_refs=tuple(refs),
    )


def validate_catalogue(items: object) -> tuple[CatalogueItem, ...]:
    """Validate a whole catalogue and refuse duplicate slugs.

    Slug uniqueness is what makes the tie-break in `app.decision_engine.rank`
    total: two items sharing a slug would leave their relative order undefined,
    which `ADR-0059`'s byte-identical requirement does not permit.
    """
    if not isinstance(items, (tuple, list)):
        raise InvalidCatalogueItem("catalogue", "catalogue must be a sequence of items")

    validated: list[CatalogueItem] = []
    for item in items:
        validated.append(
            item
            if isinstance(item, CatalogueItem)
            else validate_item(
                slug=item.get("slug"),
                title=item.get("title"),
                topics=item.get("topics"),
                difficulty=item.get("difficulty"),
                external_refs=item.get("external_refs", ()),
            )
        )

    slugs = [i.slug for i in validated]
    duplicates = sorted({s for s in slugs if slugs.count(s) > 1})
    if duplicates:
        raise InvalidCatalogueItem("slug", f"duplicate slugs in catalogue: {duplicates}")

    return tuple(validated)
