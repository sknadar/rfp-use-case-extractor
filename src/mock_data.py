"""
mock_data.py
============

Development / demo data used when `USE_MOCK_DATA=true`.

Why this exists
---------------
Every part of the pipeline except the Gemini call can be exercised for free:
upload -> read PDF -> build hierarchy -> validate -> review -> Excel -> Word.
That makes development, testing and demos possible with no API key and no cost.

The mock deliberately includes imperfect records (a missing page, a near
duplicate) so the validation and human-review screens can be demonstrated.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Raw records in exactly the shape Gemini is asked to return.
MOCK_RAW_REQUIREMENTS: List[Dict[str, Any]] = [
    {
        "section": "Customer Management",
        "sub_section": "Authentication",
        "feature": "Login",
        "requirement": "Customer shall login using registered mobile number.",
        "source_pages": [1],
        "business_context": "",
        "confidence": "high",
        "extraction_notes": "",
    },
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
        "requirement": (
            "Customers shall be able to download their account statement in PDF format."
        ),
        "source_pages": [1],
        "business_context": "",
        "confidence": "high",
        "extraction_notes": "",
    },
    {
        "section": "Transactions",
        "sub_section": "Fund Transfer",
        "feature": "High Value Transfer Verification",
        "requirement": (
            "The system shall require additional verification for high-value transfers."
        ),
        "source_pages": [2],
        "business_context": "Requirement is intended to reduce fraudulent transactions.",
        "confidence": "high",
        "extraction_notes": "",
    },
    {
        "section": "Transactions",
        "sub_section": "Notifications",
        "feature": "Transaction Alerts",
        "requirement": (
            "Customers shall receive an email notification for transactions "
            "above 1 lakh rupees."
        ),
        "source_pages": [2],
        "business_context": "",
        "confidence": "medium",
        "extraction_notes": "",
    },
    {
        "section": "Reporting",
        "sub_section": "Operational Reports",
        "feature": "Monthly Transaction Report",
        "requirement": (
            "The system shall allow administrators to generate monthly "
            "transaction reports."
        ),
        "source_pages": [3],
        "business_context": "",
        "confidence": "high",
        "extraction_notes": "",
    },
    {
        "section": "Reporting",
        "sub_section": "Operational Reports",
        "feature": "Report Export",
        "requirement": "Reports shall be exportable in Excel format.",
        "source_pages": [3],
        "business_context": "",
        "confidence": "high",
        "extraction_notes": "",
    },
    {
        # Deliberately imperfect: no page reference -> must be flagged for review.
        "section": "Security",
        "sub_section": "Access Control",
        "feature": "Role Based Access",
        "requirement": (
            "The system shall restrict administrative functions to authorised users."
        ),
        "source_pages": [],
        "business_context": "",
        "confidence": "low",
        "extraction_notes": "Page reference could not be determined.",
    },
    {
        # Deliberately a near duplicate of the balance requirement above.
        "section": "Customer Management",
        "sub_section": "Account Information",
        "feature": "Balance Enquiry",
        "requirement": "The system shall allow customers to view account balance.",
        "source_pages": [4],
        "business_context": "",
        "confidence": "medium",
        "extraction_notes": "",
    },
]


def get_mock_raw_requirements(page_count: int = 4) -> List[Dict[str, Any]]:
    """
    Return the mock records, with page numbers clamped to the real document.

    Clamping matters because the validator rejects page numbers outside the
    document, and a two-page test PDF should not produce "page 4" records.
    """
    result: List[Dict[str, Any]] = []
    for item in MOCK_RAW_REQUIREMENTS:
        copy = dict(item)
        copy["source_pages"] = [
            min(page, max(page_count, 1)) for page in item["source_pages"]
        ]
        result.append(copy)
    return result
