"""
app.py
======

The Streamlit user interface - and only the user interface.

This file collects input, shows status, displays results and offers downloads.
All real work is delegated to the modules in `src/`. Keeping it this way means
the same pipeline could later be driven by a command-line script or an API
without rewriting any business logic.

Run it with:  streamlit run app.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from config import load_settings, safe_filename
from src.excel_report import ExcelReportError, build_excel_report
from src.extractor import ExtractionError, extract_requirements
from src.hierarchy import build_hierarchy, compute_stats, iter_hierarchy
from src.logging_config import get_logger, setup_logging
from src.pdf_reader import PdfValidationError, read_pdf
from src.records import UNCLASSIFIED, clean_pages, format_pages
from src.theme import (
    inject_theme,
    render_config_line,
    render_dossier_card,
    render_ledger_strip,
    render_letterhead,
    render_status_pill,
)
from src.validator import revalidate_after_review, validate_records
from src.word_report import WordReportError, build_word_report

SETTINGS = load_settings()
setup_logging(SETTINGS.log_level)
logger = get_logger(__name__)

st.set_page_config(page_title="RFP Use Case Extractor", page_icon="📄", layout="wide")
inject_theme()

# Columns the reviewer is allowed to edit, in display order.
EDITABLE_COLUMNS = [
    "Section",
    "Sub-Section",
    "Feature",
    "Requirement",
    "Source Page",
    "Business Context",
]
DISPLAY_COLUMNS = ["ID"] + EDITABLE_COLUMNS + ["Confidence", "Review", "Review Reasons"]


# ---------------------------------------------------------------------------
# Session state - Streamlit reruns this script on every click, so anything we
# want to survive a click has to live in st.session_state.
# ---------------------------------------------------------------------------
def init_state() -> None:
    defaults: Dict[str, Any] = {
        "document": None,
        "records": [],
        "summary": None,
        "extraction": None,
        "reports": {},
        "ran": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_results() -> None:
    st.session_state.records = []
    st.session_state.summary = None
    st.session_state.extraction = None
    st.session_state.reports = {}
    st.session_state.ran = False


# ---------------------------------------------------------------------------
# Conversion helpers between our records and the editable table
# ---------------------------------------------------------------------------
def records_to_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in records:
        rows.append(
            {
                "ID": record.get("requirement_id", ""),
                "Section": record.get("section", ""),
                "Sub-Section": record.get("sub_section", ""),
                "Feature": record.get("feature", ""),
                "Requirement": record.get("requirement", ""),
                "Source Page": format_pages(record.get("source_pages")),
                "Business Context": record.get("business_context", ""),
                "Confidence": record.get("confidence", ""),
                "Review": "⚠️ Yes" if record.get("review_required") else "OK",
                "Review Reasons": "; ".join(record.get("review_reasons") or []),
            }
        )
    return pd.DataFrame(rows, columns=DISPLAY_COLUMNS)


def dataframe_to_records(
    edited: pd.DataFrame, originals: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge the reviewer's edits back into the original records.

    Fields the reviewer cannot edit (timestamps, IDs) are preserved, and any
    changed record is marked `modified_by_reviewer` for the audit trail.
    """
    by_id = {record.get("requirement_id"): record for record in originals}
    merged: List[Dict[str, Any]] = []

    for _, row in edited.iterrows():
        original = by_id.get(row["ID"])
        if original is None:
            continue

        updated = dict(original)
        new_values = {
            "section": str(row["Section"]).strip(),
            "sub_section": str(row["Sub-Section"]).strip(),
            "feature": str(row["Feature"]).strip(),
            "requirement": str(row["Requirement"]).strip(),
            "source_pages": _parse_pages(row["Source Page"]),
            "business_context": str(row["Business Context"]).strip(),
        }

        changed = any(updated.get(key) != value for key, value in new_values.items())
        updated.update(new_values)
        if changed:
            updated["modified_by_reviewer"] = True
        merged.append(updated)

    return merged


def _parse_pages(value: Any) -> List[int]:
    """Read '3, 4' or '3' or 'NOT FOUND' from the table back into [3, 4] / []."""
    text = str(value or "").strip()
    if not text or text.upper() == "NOT FOUND":
        return []
    parts = text.replace(";", ",").split(",")
    return clean_pages(parts)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar() -> None:
    with st.sidebar:
        st.subheader("Session")

        if SETTINGS.use_mock_data:
            render_status_pill("warn", "Mock mode is on. Sample data is used, Gemini is not called.")
        elif SETTINGS.google_api_key:
            render_status_pill("ok", "Gemini API key detected")
        else:
            render_status_pill(
                "error", "No Gemini API key found. Add GOOGLE_API_KEY, or set USE_MOCK_DATA=true."
            )

        st.markdown("<br>", unsafe_allow_html=True)
        render_config_line("Model", SETTINGS.model_name)
        render_config_line("Batch size", f"{SETTINGS.batch_char_budget:,} chars")
        render_config_line("Max upload", f"{SETTINGS.max_upload_mb} MB")

        st.divider()
        st.caption(
            "The API key is read from environment variables or Streamlit "
            "secrets. It is never displayed or stored by this application."
        )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_pipeline(file_bytes: bytes, file_name: str) -> None:
    """Upload -> read -> extract -> validate -> ready for review."""
    status_box = st.status("Starting extraction...", expanded=True)

    try:
        status_box.write("1/6  PDF uploaded.")
        status_box.write("2/6  Reading document page by page...")
        document = read_pdf(
            file_bytes,
            file_name,
            max_mb=SETTINGS.max_upload_mb,
            min_chars_per_page=SETTINGS.min_chars_per_page_for_text_pdf,
        )
        st.session_state.document = document
        status_box.write(
            f"     Read {document.page_count} page(s), "
            f"{document.total_chars:,} characters."
        )
        if document.likely_scanned:
            status_box.write(
                "     Warning: most pages contain little or no text. "
                "This document may be scanned; results will be incomplete."
            )

        status_box.write("3/6  Preparing content and sending it for analysis...")
        extraction = extract_requirements(
            document, SETTINGS, progress=lambda msg: status_box.write(f"     {msg}")
        )
        st.session_state.extraction = extraction
        status_box.write(f"4/6  Extraction returned {len(extraction.records)} requirement(s).")

        status_box.write("5/6  Validating output...")
        records, summary = validate_records(extraction.records, document.page_numbers())
        st.session_state.records = records
        st.session_state.summary = summary
        status_box.write(
            f"     {summary.review_required} record(s) flagged for human review."
        )

        status_box.write("6/6  Building hierarchy... done.")
        st.session_state.ran = True
        status_box.update(label="Extraction completed.", state="complete", expanded=False)

    except PdfValidationError as exc:
        status_box.update(label="Could not read the PDF.", state="error")
        st.error(str(exc))
        logger.warning("PDF rejected: %s", exc)
    except ExtractionError as exc:
        status_box.update(label="Extraction failed.", state="error")
        st.error(str(exc))
        logger.error("Extraction failed: %s", exc)
    except Exception as exc:  # last-resort safety net
        status_box.update(label="Unexpected error.", state="error")
        st.error(
            "Something went wrong while processing the document. "
            "Please try again, or try a different PDF."
        )
        logger.error("Unexpected failure: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Result screens
# ---------------------------------------------------------------------------
def render_metrics() -> None:
    document = st.session_state.document
    records = st.session_state.records
    stats = compute_stats(records)

    render_ledger_strip(
        [
            {"value": document.page_count if document else 0, "label": "Pages read"},
            {"value": stats.requirement_count, "label": "Requirements"},
            {"value": stats.section_count, "label": "Sections"},
            {"value": stats.feature_count, "label": "Features"},
            {
                "value": stats.review_required_count,
                "label": "Need review",
                "tone": "ok" if stats.review_required_count == 0 else "flag",
            },
        ]
    )

    extraction = st.session_state.extraction
    if extraction:
        for warning in extraction.warnings:
            st.warning(warning)
        if extraction.has_failures:
            with st.expander("Page ranges that could not be analysed"):
                st.table(pd.DataFrame(extraction.failed_batches))


def render_review_table() -> None:
    st.subheader("Review extracted requirements")
    st.caption(
        "Edit any cell to correct the AI output. Source Page accepts one or "
        "more page numbers, e.g. 35 or 35, 36. Then press "
        "'Save changes and re-validate'."
    )

    records = st.session_state.records
    dataframe = records_to_dataframe(records)

    edited = st.data_editor(
        dataframe,
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key="review_editor",
        column_config={
            "ID": st.column_config.TextColumn("ID", disabled=True, width="small"),
            "Requirement": st.column_config.TextColumn("Requirement", width="large"),
            "Source Page": st.column_config.TextColumn("Source Page", width="small"),
            "Confidence": st.column_config.TextColumn("Confidence", disabled=True, width="small"),
            "Review": st.column_config.TextColumn("Review", disabled=True, width="small"),
            "Review Reasons": st.column_config.TextColumn(
                "Review Reasons", disabled=True, width="large"
            ),
        },
    )

    left, right = st.columns([1, 3])
    if left.button("Save changes and re-validate", type="primary"):
        document = st.session_state.document
        merged = dataframe_to_records(edited, records)
        revalidated, summary = revalidate_after_review(merged, document.page_numbers())
        st.session_state.records = revalidated
        st.session_state.summary = summary
        st.session_state.reports = {}   # reports must be rebuilt from new data
        right.success(
            f"Saved. {summary.review_required} record(s) still need review."
        )
        st.rerun()


def render_hierarchy_view() -> None:
    st.subheader("Requirement hierarchy")
    tree = build_hierarchy(st.session_state.records)

    for section, sub_sections in tree.items():
        with st.expander(section, expanded=False):
            for sub_section, features in sub_sections.items():
                if sub_section != UNCLASSIFIED:
                    st.markdown(
                        f'<div class="dossier-subsection">{sub_section}</div>',
                        unsafe_allow_html=True,
                    )
                for feature, items in features.items():
                    if feature != UNCLASSIFIED:
                        st.markdown(f"**{feature}**")
                    for record in items:
                        render_dossier_card(record, format_pages)


def render_downloads() -> None:
    st.subheader("Reports")
    document = st.session_state.document
    records = st.session_state.records
    base_name = safe_filename(document.file_name if document else "rfp_document")
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    extraction = st.session_state.extraction

    extra = {
        "Extraction mode": extraction.mode if extraction else "unknown",
        "Model": SETTINGS.model_name,
    }

    if st.button("Generate Excel and Word reports", type="primary"):
        try:
            st.session_state.reports = {
                "excel": build_excel_report(
                    records, document.file_name, document.page_count, extra
                ),
                "word": build_word_report(
                    records, document.file_name, document.page_count, extra
                ),
            }
            st.success("Reports generated.")
        except ExcelReportError as exc:
            st.error(str(exc))
        except WordReportError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error("The reports could not be created.")
            logger.error("Report generation failed: %s", exc, exc_info=True)

    reports = st.session_state.reports
    if reports:
        left, right = st.columns(2)
        left.download_button(
            "⬇️ Download Excel (.xlsx)",
            data=reports["excel"],
            file_name=f"{base_name}_requirements_{stamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        right.download_button(
            "⬇️ Download Word (.docx)",
            data=reports["word"],
            file_name=f"{base_name}_requirements_{stamp}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
        )


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------
def main() -> None:
    init_state()

    render_letterhead(
        "RFP Use Case Extractor",
        "AI-powered extraction of structured requirements from RFP PDF documents. "
        "Every requirement is extracted from what the RFP explicitly states and carries the page it came from.",
    )

    render_sidebar()

    uploaded = st.file_uploader("Upload an RFP document (PDF only)", type=["pdf"])

    left, right = st.columns([1, 4])
    run_clicked = left.button("Run Extraction", type="primary", disabled=uploaded is None)
    if uploaded is None:
        right.info("Select a PDF file to enable extraction.")

    if run_clicked and uploaded is not None:
        reset_results()
        run_pipeline(uploaded.getvalue(), uploaded.name)

    if st.session_state.ran:
        st.divider()
        render_metrics()

        if not st.session_state.records:
            st.warning(
                "No explicit requirements were extracted from this document. "
                "This can happen when the PDF is mostly commercial or "
                "administrative text rather than requirements."
            )
            return

        st.divider()
        tab_review, tab_hierarchy, tab_reports = st.tabs(
            ["Review", "Hierarchy", "Reports"]
        )
        with tab_review:
            render_review_table()
        with tab_hierarchy:
            render_hierarchy_view()
        with tab_reports:
            render_downloads()


if __name__ == "__main__":
    main()
