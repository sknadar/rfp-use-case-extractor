"""
validator.py
============

Never trust AI output blindly.

This module checks every extracted record before it is allowed anywhere near a
report. The golden rule of this file: **flag, do not delete.** A record that
fails a check is marked `review_required` with a human-readable reason, so a
person decides what to do - nothing disappears silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Sequence

from src.logging_config import get_logger
from src.records import CONFIDENCE_VALUES, UNCLASSIFIED, clean_pages

logger = get_logger(__name__)

# Two requirements this similar are treated as possible duplicates.
NEAR_DUPLICATE_THRESHOLD = 0.92
# Anything shorter than this is unlikely to be a real requirement sentence.
MIN_REQUIREMENT_LENGTH = 12


@dataclass
class ValidationSummary:
    """Counts the UI shows after validation."""

    total: int = 0
    review_required: int = 0
    missing_pages: int = 0
    invalid_pages: int = 0
    missing_hierarchy: int = 0
    empty_requirements: int = 0
    exact_duplicates: int = 0
    near_duplicates: int = 0
    messages: List[str] = field(default_factory=list)


def validate_records(
    records: Sequence[Dict[str, Any]],
    valid_page_numbers: Sequence[int],
) -> tuple[List[Dict[str, Any]], ValidationSummary]:
    """
    Check every record and return (validated_records, summary).

    `valid_page_numbers` comes from the PDF reader, so a page reference can be
    checked against the pages that actually exist in the uploaded document.
    """
    valid_pages = set(int(p) for p in valid_page_numbers)
    summary = ValidationSummary(total=len(records))
    validated: List[Dict[str, Any]] = []

    for record in records:
        checked = _validate_one(dict(record), valid_pages, summary)
        validated.append(checked)

    _detect_duplicates(validated, summary)

    for record in validated:
        if record["review_required"]:
            summary.review_required += 1

    logger.info(
        "Requirements validated | total=%s | review_required=%s",
        summary.total,
        summary.review_required,
    )
    return validated, summary


# ---------------------------------------------------------------------------
# Per-record checks
# ---------------------------------------------------------------------------
def _validate_one(
    record: Dict[str, Any], valid_pages: set[int], summary: ValidationSummary
) -> Dict[str, Any]:
    reasons: List[str] = list(record.get("review_reasons") or [])

    # --- normalise types first so later checks are safe --------------------
    for key in ("section", "sub_section", "feature", "requirement", "business_context"):
        record[key] = str(record.get(key) or "").strip()
    record["source_pages"] = clean_pages(record.get("source_pages"))

    confidence = str(record.get("confidence") or "medium").strip().lower()
    record["confidence"] = confidence if confidence in CONFIDENCE_VALUES else "medium"

    # --- requirement text ---------------------------------------------------
    if not record["requirement"]:
        reasons.append("Requirement text is empty.")
        summary.empty_requirements += 1
    elif len(record["requirement"]) < MIN_REQUIREMENT_LENGTH:
        reasons.append("Requirement text is suspiciously short.")

    # --- hierarchy ----------------------------------------------------------
    # A blank field is filled with UNCLASSIFIED before this check runs, so
    # "empty" and "the model wrote Unclassified" are handled the same way.
    for key in ("section", "sub_section", "feature"):
        if not record[key]:
            record[key] = UNCLASSIFIED

    unclassified_levels = [
        label
        for key, label in (
            ("section", "Section"),
            ("sub_section", "Sub-Section"),
            ("feature", "Feature"),
        )
        if record[key] == UNCLASSIFIED
    ]

    if unclassified_levels:
        summary.missing_hierarchy += 1
        # Many real RFPs have genuinely flat sections with no numbered
        # sub-heading - a confident "Unclassified" for Sub-Section or Feature
        # there is a correct answer, not an error, and should not swamp the
        # review queue. Only raise a flag when the model itself was unsure
        # (confidence below "high"), or when even the top-level Section is
        # missing, since that is a more serious gap worth a human's attention
        # regardless of confidence.
        if record["confidence"] != "high" or "Section" in unclassified_levels:
            reasons.append(
                f"Hierarchy could not be determined for: "
                f"{', '.join(unclassified_levels)}."
            )

    # --- page traceability (mandatory) -------------------------------------
    pages = record["source_pages"]
    if not pages:
        summary.missing_pages += 1
        reasons.append("No source page - traceability missing.")
    else:
        out_of_range = [p for p in pages if p < 1 or (valid_pages and p not in valid_pages)]
        if out_of_range:
            summary.invalid_pages += 1
            pretty = ", ".join(str(p) for p in out_of_range)
            reasons.append(f"Page reference outside the document: {pretty}.")

    # --- low confidence -----------------------------------------------------
    if record["confidence"] == "low":
        reasons.append("Model reported low confidence.")

    if record.get("extraction_notes"):
        reasons.append(f"Extraction note: {record['extraction_notes']}")

    record["review_reasons"] = _dedupe_keep_order(reasons)
    record["review_required"] = bool(record["review_reasons"])
    return record


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------
_PUNCTUATION = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE = re.compile(r"\s+")


def normalise_text(text: str) -> str:
    """Lower-case, strip punctuation and collapse spaces - for comparison only."""
    lowered = str(text or "").lower()
    lowered = _PUNCTUATION.sub(" ", lowered)
    return _WHITESPACE.sub(" ", lowered).strip()


def _detect_duplicates(records: List[Dict[str, Any]], summary: ValidationSummary) -> None:
    """
    Flag exact and near duplicates. Nothing is removed.

    Large RFPs legitimately repeat requirements across sections, so deleting
    automatically would destroy real content. A human decides.
    """
    seen: Dict[str, str] = {}          # normalised text -> requirement_id
    normalised: List[tuple[str, str, Dict[str, Any]]] = []

    for record in records:
        key = normalise_text(record.get("requirement", ""))
        if not key:
            continue

        if key in seen:
            summary.exact_duplicates += 1
            reason = f"Exact duplicate of {seen[key]}."
            record["review_reasons"] = _dedupe_keep_order(
                list(record.get("review_reasons") or []) + [reason]
            )
            record["review_required"] = True
        else:
            seen[key] = record.get("requirement_id", "?")
            normalised.append((key, record.get("requirement_id", "?"), record))

    # Near duplicates: only compare records of similar length (cheap filter).
    for i in range(len(normalised)):
        key_i, id_i, rec_i = normalised[i]
        for j in range(i + 1, len(normalised)):
            key_j, id_j, rec_j = normalised[j]
            if abs(len(key_i) - len(key_j)) > 0.25 * max(len(key_i), len(key_j)):
                continue
            ratio = SequenceMatcher(None, key_i, key_j).ratio()
            if ratio >= NEAR_DUPLICATE_THRESHOLD:
                summary.near_duplicates += 1
                note = f"Possible duplicate of {id_i} (similarity {ratio:.0%})."
                rec_j["review_reasons"] = _dedupe_keep_order(
                    list(rec_j.get("review_reasons") or []) + [note]
                )
                rec_j["review_required"] = True


def _dedupe_keep_order(items: Sequence[str]) -> List[str]:
    out: List[str] = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out


# ---------------------------------------------------------------------------
# Used after the human review screen
# ---------------------------------------------------------------------------
def revalidate_after_review(
    records: Sequence[Dict[str, Any]],
    valid_page_numbers: Sequence[int],
) -> tuple[List[Dict[str, Any]], ValidationSummary]:
    """
    Re-run validation on records a human has edited.

    Review reasons are cleared first, so a corrected record can lose its flag.
    The `modified_by_reviewer` marker is preserved for the audit trail.
    """
    cleaned = []
    for record in records:
        copy = dict(record)
        copy["review_reasons"] = []
        copy["review_required"] = False
        cleaned.append(copy)
    return validate_records(cleaned, valid_page_numbers)
