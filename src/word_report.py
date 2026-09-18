"""
word_report.py
==============

Single responsibility: write the .docx report with python-docx.

Structure:
    Title
    Executive Summary (document name, pages, counts, review count)
    Heading 1  = Section
    Heading 2  = Sub-Section
    Heading 3  = Feature
    Body       = Requirement / Source Page / Business Context

Using real Word heading styles (not just bold text) means the document gets a
working navigation pane and can generate a table of contents in Word.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from src.hierarchy import build_hierarchy, compute_stats, iter_hierarchy
from src.logging_config import get_logger
from src.records import UNCLASSIFIED, format_pages

logger = get_logger(__name__)

INK_COLOUR = RGBColor(0x16, 0x23, 0x3B)      # ink navy, matches the app
REVIEW_COLOUR = RGBColor(0xA6, 0x40, 0x2C)   # clay, matches the app
MUTED_COLOUR = RGBColor(0x3B, 0x4B, 0x63)    # ink-soft, matches the app


class WordReportError(Exception):
    """Raised when the Word document cannot be produced."""


def build_word_report(
    records: Sequence[Dict[str, Any]],
    document_name: str,
    page_count: int,
    extra_summary: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Build the .docx report and return it as bytes."""
    try:
        document = Document()
        _set_base_font(document)

        _write_title(document, document_name)
        _write_executive_summary(document, records, document_name, page_count, extra_summary)
        _write_requirements(document, records)

        stream = io.BytesIO()
        document.save(stream)
        logger.info("Word generated | requirements=%s", len(records))
        return stream.getvalue()
    except Exception as exc:
        logger.error("Word generation failed: %s", exc, exc_info=True)
        raise WordReportError(
            "The Word report could not be created. Please try again."
        ) from exc


def _set_base_font(document: Document) -> None:
    style = document.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(10.5)

    # Word's built-in heading styles default to a blue theme colour. Recolour
    # them to the app's ink navy and a Georgia serif (available on Windows,
    # macOS and most Linux installs, so the document looks right without
    # requiring the reader to have any special font installed) so the
    # document, the app and the Excel report all read as one product.
    for style_name in ("Title", "Heading 1", "Heading 2", "Heading 3", "Heading 4"):
        try:
            heading_style = document.styles[style_name]
        except KeyError:
            continue
        heading_style.font.name = "Georgia"
        heading_style.font.color.rgb = INK_COLOUR


def _write_title(document: Document, document_name: str) -> None:
    heading = document.add_heading("RFP Use Case Extraction Report", level=0)
    heading.alignment = WD_ALIGN_PARAGRAPH.LEFT

    subtitle = document.add_paragraph()
    run = subtitle.add_run(
        f"Source document: {document_name}    |    "
        f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}"
    )
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED_COLOUR


def _write_executive_summary(
    document: Document,
    records: Sequence[Dict[str, Any]],
    document_name: str,
    page_count: int,
    extra_summary: Optional[Dict[str, Any]],
) -> None:
    stats = compute_stats(records)
    traced = sum(1 for r in records if r.get("source_pages"))

    document.add_heading("Executive Summary", level=1)

    table = document.add_table(rows=0, cols=2)
    table.style = "Table Grid"

    rows = [
        ("Document name", document_name),
        ("Pages in document", str(page_count)),
        ("Requirements extracted", str(stats.requirement_count)),
        ("Sections", str(stats.section_count)),
        ("Sub-sections", str(stats.sub_section_count)),
        ("Features", str(stats.feature_count)),
        ("Requirements with a source page", f"{traced} of {stats.requirement_count}"),
        ("Requirements requiring review", str(stats.review_required_count)),
    ]
    for key, value in (extra_summary or {}).items():
        rows.append((str(key), str(value)))

    for label, value in rows:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value
        for paragraph in cells[0].paragraphs:
            for run in paragraph.runs:
                run.bold = True

    note = document.add_paragraph()
    run = note.add_run(
        "All requirements below were extracted from the source RFP. Each entry "
        "carries the page number it was taken from, so any statement can be "
        "traced back to the original document. Entries marked REVIEW REQUIRED "
        "need human confirmation before use."
    )
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED_COLOUR


def _write_requirements(document: Document, records: Sequence[Dict[str, Any]]) -> None:
    document.add_heading("Extracted Requirements", level=1)

    if not records:
        document.add_paragraph(
            "No requirements were extracted from this document."
        )
        return

    tree = build_hierarchy(records)
    current_section: Optional[str] = None
    current_sub_section: Optional[tuple] = None

    for section, sub_section, feature, items in iter_hierarchy(tree):
        if section != current_section:
            document.add_heading(section, level=2)
            current_section = section
            current_sub_section = None

        if (section, sub_section) != current_sub_section:
            # Skip the heading entirely when there genuinely is no
            # sub-section in the source document, rather than printing the
            # word "Unclassified" as if it were a real heading.
            if sub_section != UNCLASSIFIED:
                document.add_heading(sub_section, level=3)
            current_sub_section = (section, sub_section)

        if feature != UNCLASSIFIED:
            document.add_heading(feature, level=4)

        for record in items:
            _write_one_requirement(document, record)


def _write_one_requirement(document: Document, record: Dict[str, Any]) -> None:
    paragraph = document.add_paragraph(style="List Bullet")
    id_run = paragraph.add_run(f"[{record.get('requirement_id', '')}] ")
    id_run.bold = True
    paragraph.add_run(record.get("requirement", ""))

    detail = document.add_paragraph()
    detail.paragraph_format.left_indent = Pt(24)
    page_run = detail.add_run(f"Source Page: {format_pages(record.get('source_pages'))}")
    page_run.font.size = Pt(9)
    page_run.bold = True

    context = (record.get("business_context") or "").strip()
    if context:
        context_paragraph = document.add_paragraph()
        context_paragraph.paragraph_format.left_indent = Pt(24)
        run = context_paragraph.add_run(f"Business Context: {context}")
        run.font.size = Pt(9)
        run.italic = True
        run.font.color.rgb = MUTED_COLOUR

    if record.get("review_required"):
        review_paragraph = document.add_paragraph()
        review_paragraph.paragraph_format.left_indent = Pt(24)
        reasons = "; ".join(record.get("review_reasons") or []) or "Flagged for review."
        run = review_paragraph.add_run(f"REVIEW REQUIRED: {reasons}")
        run.font.size = Pt(9)
        run.bold = True
        run.font.color.rgb = REVIEW_COLOUR
