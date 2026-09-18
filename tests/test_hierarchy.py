"""Tests for hierarchy.py: grouping, counting and flattening."""

from __future__ import annotations

from src.hierarchy import build_hierarchy, compute_stats, flatten_hierarchy, iter_hierarchy
from src.records import UNCLASSIFIED, make_record


def test_hierarchy_has_four_levels(records):
    tree = build_hierarchy(records)

    assert set(tree.keys()) == {"Customer Management", "Reporting"}
    assert "Account Information" in tree["Customer Management"]
    assert "Balance Enquiry" in tree["Customer Management"]["Account Information"]
    requirement = tree["Customer Management"]["Account Information"]["Balance Enquiry"][0]
    assert requirement["source_pages"] == [1]


def test_multiple_requirements_can_share_one_feature():
    raws = [
        {
            "section": "Reporting",
            "sub_section": "Operational Reports",
            "feature": "Report Export",
            "requirement": "Reports shall be exportable in Excel format.",
            "source_pages": [3],
        },
        {
            "section": "Reporting",
            "sub_section": "Operational Reports",
            "feature": "Report Export",
            "requirement": "Reports shall be exportable in PDF format.",
            "source_pages": [3],
        },
    ]
    records = [make_record(r, f"REQ-{i:04d}") for i, r in enumerate(raws, start=1)]
    tree = build_hierarchy(records)

    assert len(tree["Reporting"]["Operational Reports"]["Report Export"]) == 2


def test_missing_levels_fall_back_to_unclassified():
    record = make_record({"requirement": "Something shall happen."}, "REQ-0001")
    tree = build_hierarchy([record])

    assert UNCLASSIFIED in tree
    assert UNCLASSIFIED in tree[UNCLASSIFIED]


def test_stats_count_each_level_once(records):
    stats = compute_stats(records)

    assert stats.requirement_count == 3
    assert stats.section_count == 2
    assert stats.sub_section_count == 2
    assert stats.feature_count == 3
    assert stats.pages_referenced == [1, 2]


def test_flatten_returns_every_record(records):
    tree = build_hierarchy(records)

    assert len(flatten_hierarchy(tree)) == len(records)
    assert len(list(iter_hierarchy(tree))) == 3      # three distinct features
