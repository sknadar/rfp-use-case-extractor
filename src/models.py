"""
models.py
=========

The data contract between Gemini and our Python code.

Why Pydantic?
-------------
LangChain can force a chat model to reply in the exact shape of a Pydantic model
(`llm.with_structured_output(Model)`). Instead of parsing free text with regular
expressions, we receive validated Python objects. If the model answers in the
wrong shape we find out immediately instead of halfway through report
generation.

Note the `description=` text on every field: LangChain turns this model into a
JSON schema and sends it to Gemini, so these descriptions are part of the
prompt. They are written for the model to read.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from src.records import (  # re-exported so callers only need one import
    ALL_FIELDS,
    CONFIDENCE_VALUES,
    MANDATORY_FIELDS,
    UNCLASSIFIED,
    make_record,
)

__all__ = [
    "RawRequirement",
    "ExtractionResponse",
    "raw_to_record",
    "ALL_FIELDS",
    "MANDATORY_FIELDS",
    "CONFIDENCE_VALUES",
    "UNCLASSIFIED",
]


class RawRequirement(BaseModel):
    """One explicit requirement exactly as returned by Gemini."""

    section: str = Field(
        description=(
            "Top-level business area, taken from the RFP's own wording "
            "(for example 'Customer Management'). Use the exact word "
            "'Unclassified' if the document does not support any section."
        )
    )
    sub_section: str = Field(
        description=(
            "Second level inside the section (for example 'Authentication'). "
            "Use 'Unclassified' if the document does not support one."
        )
    )
    feature: str = Field(
        description=(
            "The specific capability the requirement describes (for example "
            "'Login'). Use 'Unclassified' if the document does not support one."
        )
    )
    requirement: str = Field(
        description=(
            "One single explicit requirement as stated in the RFP. Keep the "
            "customer's meaning and stay close to the source wording. Never add "
            "any detail that is not in the source text."
        )
    )
    source_pages: List[int] = Field(
        default_factory=list,
        description=(
            "Page number(s) this requirement came from, taken from the "
            "'=== PAGE n ===' markers. Never guess. Return an empty list if you "
            "cannot tell."
        ),
    )
    business_context: str = Field(
        default="",
        description=(
            "Background from the RFP explaining why the requirement exists. "
            "Empty string if the document gives none. This is never itself a "
            "requirement."
        ),
    )
    confidence: str = Field(
        default="medium",
        description=(
            "'high', 'medium' or 'low' - how confident you are that this is an "
            "explicit requirement with a correct hierarchy and page reference."
        ),
    )
    extraction_notes: str = Field(
        default="",
        description=(
            "Short note for the human reviewer, for example 'section not stated "
            "in document'. Empty string when there is nothing to flag."
        ),
    )


class ExtractionResponse(BaseModel):
    """The complete answer for one batch of pages."""

    requirements: List[RawRequirement] = Field(
        default_factory=list,
        description=(
            "Every explicit requirement found in the supplied pages. An empty "
            "list is a valid answer when the pages contain no requirements."
        ),
    )


def raw_to_record(raw: RawRequirement, requirement_id: str) -> Dict[str, Any]:
    """Convert a Gemini answer object into the plain dict used downstream."""
    payload: Dict[str, Any] = raw.model_dump()
    return make_record(payload, requirement_id)
