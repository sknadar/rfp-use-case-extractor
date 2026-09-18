"""
hierarchy.py
============

Turns a flat list of requirement dictionaries into the four-level business
structure the reports need:

    Section -> Sub-Section -> Feature -> Requirement

The output is an ordinary nested dictionary (`dict` of `dict` of `dict` of
`list`), which Python 3.7+ keeps in insertion order. First appearance in the
document therefore decides the order in the report - that keeps the report
reading in the same order as the RFP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from src.logging_config import get_logger
from src.records import UNCLASSIFIED

logger = get_logger(__name__)

# Section -> Sub-Section -> Feature -> [records]
Hierarchy = Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]]


@dataclass
class HierarchyStats:
    """Headline numbers shown in the UI and in the report summaries."""

    requirement_count: int = 0
    section_count: int = 0
    sub_section_count: int = 0
    feature_count: int = 0
    review_required_count: int = 0
    pages_referenced: List[int] = field(default_factory=list)


def build_hierarchy(records: Sequence[Dict[str, Any]]) -> Hierarchy:
    """Group records by Section, then Sub-Section, then Feature."""
    tree: Hierarchy = {}

    for record in records:
        section = record.get("section") or UNCLASSIFIED
        sub_section = record.get("sub_section") or UNCLASSIFIED
        feature = record.get("feature") or UNCLASSIFIED

        tree.setdefault(section, {})
        tree[section].setdefault(sub_section, {})
        tree[section][sub_section].setdefault(feature, [])
        tree[section][sub_section][feature].append(record)

    logger.info("Hierarchy built | sections=%s", len(tree))
    return tree


def compute_stats(records: Sequence[Dict[str, Any]]) -> HierarchyStats:
    """Count sections, sub-sections, features, reviews and referenced pages."""
    sections: set[str] = set()
    sub_sections: set[tuple[str, str]] = set()
    features: set[tuple[str, str, str]] = set()
    pages: set[int] = set()
    review = 0

    for record in records:
        section = record.get("section") or UNCLASSIFIED
        sub_section = record.get("sub_section") or UNCLASSIFIED
        feature = record.get("feature") or UNCLASSIFIED

        sections.add(section)
        sub_sections.add((section, sub_section))
        features.add((section, sub_section, feature))

        for page in record.get("source_pages") or []:
            try:
                pages.add(int(page))
            except (TypeError, ValueError):
                continue

        if record.get("review_required"):
            review += 1

    return HierarchyStats(
        requirement_count=len(records),
        section_count=len(sections),
        sub_section_count=len(sub_sections),
        feature_count=len(features),
        review_required_count=review,
        pages_referenced=sorted(pages),
    )


def flatten_hierarchy(tree: Hierarchy) -> List[Dict[str, Any]]:
    """
    Walk the tree back into a flat list, in hierarchy order.

    Excel needs a flat table, so the Excel report uses this to get rows that are
    already grouped sensibly.
    """
    rows: List[Dict[str, Any]] = []
    for sub_sections in tree.values():
        for features in sub_sections.values():
            for records in features.values():
                rows.extend(records)
    return rows


def iter_hierarchy(tree: Hierarchy):
    """
    Yield (section, sub_section, feature, records) tuples in order.

    The Word report walks the document with this, one heading level at a time.
    """
    for section, sub_sections in tree.items():
        for sub_section, features in sub_sections.items():
            for feature, records in features.items():
                yield section, sub_section, feature, records
