"""
records.py
==========

The plain-Python shape of a requirement, with no AI libraries involved.

Everything downstream of extraction (validation, hierarchy, Excel, Word, the
review table) works with these dictionaries. That is deliberate: those modules
can then be unit-tested without Pydantic, LangChain or a Gemini API key.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

# The five fields the business considers mandatory.
MANDATORY_FIELDS: List[str] = [
    "section",
    "sub_section",
    "feature",
    "requirement",
    "source_pages",
]

# Every field a record carries through the pipeline.
ALL_FIELDS: List[str] = [
    "requirement_id",
    "section",
    "sub_section",
    "feature",
    "requirement",
    "source_pages",
    "business_context",
    "confidence",
    "review_required",
    "review_reasons",
    "extraction_notes",
    "extracted_at",
    "modified_by_reviewer",
]

CONFIDENCE_VALUES = ("high", "medium", "low")

# Used when a hierarchy level cannot be determined from the document.
UNCLASSIFIED = "Unclassified"


def clean_pages(pages: Any) -> List[int]:
    """Normalise any page value into a sorted list of unique integers."""
    cleaned: List[int] = []
    if pages is None:
        return cleaned
    if not isinstance(pages, (list, tuple, set)):
        pages = [pages]
    for page in pages:
        try:
            value = int(str(page).strip())
        except (TypeError, ValueError):
            continue
        if value not in cleaned:
            cleaned.append(value)
    return sorted(cleaned)


def make_record(raw: Dict[str, Any], requirement_id: str) -> Dict[str, Any]:
    """
    Build a full pipeline record from a raw extraction dictionary.

    Missing keys get safe defaults; the validator decides afterwards whether a
    record is usable or needs human review. We never silently throw a record
    away here.
    """
    confidence = str(raw.get("confidence") or "medium").strip().lower()
    if confidence not in CONFIDENCE_VALUES:
        confidence = "medium"

    return {
        "requirement_id": requirement_id,
        "section": str(raw.get("section") or "").strip(),
        "sub_section": str(raw.get("sub_section") or "").strip(),
        "feature": str(raw.get("feature") or "").strip(),
        "requirement": str(raw.get("requirement") or "").strip(),
        "source_pages": clean_pages(raw.get("source_pages")),
        "business_context": str(raw.get("business_context") or "").strip(),
        "confidence": confidence,
        "review_required": False,
        "review_reasons": [],
        "extraction_notes": str(raw.get("extraction_notes") or "").strip(),
        "extracted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "modified_by_reviewer": False,
    }


def format_pages(pages: Any) -> str:
    """Render source pages for display: [3, 4] -> '3, 4'; [] -> 'NOT FOUND'."""
    values = clean_pages(pages)
    return ", ".join(str(p) for p in values) if values else "NOT FOUND"
