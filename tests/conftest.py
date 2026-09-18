"""
conftest.py
===========

Shared test fixtures. pytest loads this file automatically.

Everything here is deliberately free of Gemini, LangChain and Streamlit, so the
whole test suite runs offline, instantly and for free.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import pytest

# Make the project root importable so `import src...` works from anywhere.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.records import make_record  # noqa: E402
from tools.simple_pdf import make_pdf  # noqa: E402

SAMPLE_PAGES = [
    "1. CUSTOMER MANAGEMENT\n"
    "The system shall allow customers to view their account balance.\n"
    "Customers shall be able to download their account statement in PDF format.",
    "2. REPORTING\n"
    "The system shall allow administrators to generate monthly transaction reports.\n"
    "Reports shall be exportable in Excel format.",
]


@pytest.fixture
def pdf_bytes() -> bytes:
    """A real two-page, text-based PDF."""
    return make_pdf(SAMPLE_PAGES)


@pytest.fixture
def blank_pdf_bytes() -> bytes:
    """A valid PDF whose pages contain no text (stands in for a scan)."""
    return make_pdf([" ", " "])


@pytest.fixture
def raw_requirements() -> List[Dict[str, Any]]:
    """Raw extraction output in the shape Gemini returns."""
    return [
        {
            "section": "Customer Management",
            "sub_section": "Account Information",
            "feature": "Balance Enquiry",
            "requirement": "The system shall allow customers to view their account balance.",
            "source_pages": [1],
            "business_context": "",
            "confidence": "high",
            "extraction_notes": "",
        },
        {
            "section": "Customer Management",
            "sub_section": "Account Information",
            "feature": "Account Statement",
            "requirement": "Customers shall be able to download their account statement in PDF format.",
            "source_pages": [1],
            "business_context": "",
            "confidence": "high",
            "extraction_notes": "",
        },
        {
            "section": "Reporting",
            "sub_section": "Operational Reports",
            "feature": "Monthly Transaction Report",
            "requirement": "The system shall allow administrators to generate monthly transaction reports.",
            "source_pages": [2],
            "business_context": "",
            "confidence": "high",
            "extraction_notes": "",
        },
    ]


@pytest.fixture
def records(raw_requirements) -> List[Dict[str, Any]]:
    """The same data converted into pipeline records."""
    return [
        make_record(raw, f"REQ-{index:04d}")
        for index, raw in enumerate(raw_requirements, start=1)
    ]
