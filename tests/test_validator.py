"""Tests for validator.py: field checks, traceability and duplicate flagging."""

from __future__ import annotations

from src.records import UNCLASSIFIED, make_record
from src.validator import revalidate_after_review, validate_records


def _record(**overrides):
    base = {
        "section": "Customer Management",
        "sub_section": "Account Information",
        "feature": "Balance Enquiry",
        "requirement": "The system shall allow customers to view their account balance.",
        "source_pages": [1],
        "business_context": "",
        "confidence": "high",
        "extraction_notes": "",
    }
    base.update(overrides)
    return make_record(base, overrides.pop("requirement_id", "REQ-0001"))


def test_valid_record_is_not_flagged(records):
    validated, summary = validate_records(records, valid_page_numbers=[1, 2])

    assert summary.total == 3
    assert summary.review_required == 0
    assert all(r["review_required"] is False for r in validated)


def test_missing_requirement_text_is_flagged():
    validated, summary = validate_records([_record(requirement="")], [1])

    assert summary.empty_requirements == 1
    assert validated[0]["review_required"] is True
    assert any("empty" in reason.lower() for reason in validated[0]["review_reasons"])


def test_missing_page_is_flagged_but_record_is_kept():
    validated, summary = validate_records([_record(source_pages=[])], [1, 2])

    assert summary.missing_pages == 1
    assert len(validated) == 1                      # nothing was deleted
    assert validated[0]["review_required"] is True
    assert any("traceability" in r.lower() for r in validated[0]["review_reasons"])


def test_page_outside_the_document_is_flagged():
    validated, summary = validate_records([_record(source_pages=[99])], [1, 2])

    assert summary.invalid_pages == 1
    assert any("outside the document" in r for r in validated[0]["review_reasons"])


def test_confident_missing_subsection_is_not_flagged():
    # Real RFPs often have flat sections with no numbered sub-heading. If the
    # model confidently reports Unclassified there, that is a correct answer
    # about the document's structure, not an extraction error - it should not
    # be sent to the review queue.
    validated, summary = validate_records(
        [_record(sub_section="", feature="", confidence="high")], [1]
    )

    assert summary.missing_hierarchy == 1     # still counted for visibility...
    assert validated[0]["sub_section"] == UNCLASSIFIED
    assert validated[0]["feature"] == UNCLASSIFIED
    assert validated[0]["review_required"] is False   # ...but not flagged


def test_low_confidence_missing_subsection_is_flagged():
    validated, _ = validate_records(
        [_record(sub_section="", confidence="medium")], [1]
    )
    assert validated[0]["review_required"] is True


def test_missing_section_is_always_flagged_even_at_high_confidence():
    # A missing top-level Section is a more serious gap than a missing
    # Sub-Section or Feature, so it is flagged regardless of confidence.
    validated, _ = validate_records([_record(section="", confidence="high")], [1])
    assert validated[0]["section"] == UNCLASSIFIED
    assert validated[0]["review_required"] is True


def test_low_confidence_is_flagged():
    validated, _ = validate_records([_record(confidence="low")], [1])
    assert validated[0]["review_required"] is True


def test_exact_duplicate_is_flagged_on_the_second_record():
    first = _record(requirement_id="REQ-0001")
    second = _record(requirement_id="REQ-0002", source_pages=[2])
    validated, summary = validate_records([first, second], [1, 2])

    assert summary.exact_duplicates == 1
    assert validated[0]["review_required"] is False
    assert validated[1]["review_required"] is True
    assert len(validated) == 2                      # duplicates are kept


def test_near_duplicate_is_flagged():
    first = _record(requirement_id="REQ-0001")
    second = _record(
        requirement_id="REQ-0002",
        requirement="The system shall allow customers to view account balance.",
        source_pages=[2],
    )
    validated, summary = validate_records([first, second], [1, 2])

    assert summary.near_duplicates == 1
    assert validated[1]["review_required"] is True


def test_reviewer_correction_clears_the_flag():
    validated, summary = validate_records([_record(source_pages=[])], [1, 2])
    assert summary.review_required == 1

    validated[0]["source_pages"] = [2]
    validated[0]["modified_by_reviewer"] = True

    revalidated, new_summary = revalidate_after_review(validated, [1, 2])

    assert new_summary.review_required == 0
    assert revalidated[0]["review_required"] is False
    assert revalidated[0]["modified_by_reviewer"] is True   # audit trail survives
