"""
theme.py
========

The visual identity for the app, kept in one file on purpose: change a colour
or a typeface here and it updates everywhere, instead of hunting through
`app.py` for scattered style strings.

Design direction ("Dossier")
-----------------------------
This tool is an audit and traceability instrument for procurement documents,
not a marketing dashboard - so the visual language borrows from a case file /
official register rather than a generic SaaS product: ink on paper, a single
brass accent used sparingly, flat panels with a structural left-rule instead
of stacked rounded cards, and monospace used only where it is functional
(requirement IDs, page numbers) rather than decorative.

A known limitation, on purpose disclosed here rather than hidden: Streamlit's
`st.data_editor` renders its grid to an internal canvas, not to styleable
HTML. The CSS below can restyle everything around that grid (header, sidebar,
tabs, buttons, the hierarchy view) but cannot recolour individual cells inside
the editable review table.
"""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

# ---------------------------------------------------------------------------
# Design tokens - the single source of truth for colour and type.
# ---------------------------------------------------------------------------
COLOR_INK = "#16233B"
COLOR_INK_SOFT = "#3B4B63"
COLOR_PAPER = "#FAF7F1"
COLOR_PAPER_RAISED = "#FFFFFF"
COLOR_RULE = "#D9D2C2"
COLOR_BRASS = "#9C6B2E"
COLOR_BRASS_SOFT = "#F1E4D2"
COLOR_CLAY = "#A6402C"
COLOR_CLAY_SOFT = "#F4E1DC"
COLOR_LEDGER_GREEN = "#3F6B4B"
COLOR_LEDGER_GREEN_SOFT = "#E1EAE3"

FONT_SERIF = "'Source Serif 4', Georgia, serif"
FONT_SANS = "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif"
FONT_MONO = "'IBM Plex Mono', 'SFMono-Regular', Consolas, monospace"


def inject_theme() -> None:
    """Load the fonts and CSS once at the top of the page."""
    st.markdown(_CSS, unsafe_allow_html=True)


_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {{
    font-family: {FONT_SANS};
    color: {COLOR_INK};
}}

.stApp {{
    background-color: {COLOR_PAPER};
}}

h1, h2, h3 {{
    font-family: {FONT_SERIF};
    color: {COLOR_INK};
    font-weight: 600;
    letter-spacing: -0.01em;
}}

/* ---- Letterhead ------------------------------------------------------- */
.dossier-letterhead {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding-bottom: 20px;
    margin-bottom: 24px;
    border-bottom: 2px solid {COLOR_INK};
}}
.dossier-letterhead .mark {{ flex-shrink: 0; }}
.dossier-letterhead .titles h1 {{
    font-size: 1.7rem;
    line-height: 1.1;
    margin: 0;
}}
.dossier-letterhead .titles p {{
    font-family: {FONT_SANS};
    font-size: 0.92rem;
    color: {COLOR_INK_SOFT};
    margin: 4px 0 0 0;
}}

/* ---- Ledger strip (summary stats) ------------------------------------ */
.ledger-strip {{
    display: flex;
    border: 1px solid {COLOR_RULE};
    background: {COLOR_PAPER_RAISED};
    margin: 4px 0 20px 0;
}}
.ledger-cell {{
    flex: 1;
    padding: 14px 18px;
    border-right: 1px solid {COLOR_RULE};
}}
.ledger-cell:last-child {{ border-right: none; }}
.ledger-cell .value {{
    font-family: {FONT_SERIF};
    font-size: 1.7rem;
    font-weight: 600;
    color: {COLOR_INK};
    line-height: 1;
}}
.ledger-cell .value.flag {{ color: {COLOR_CLAY}; }}
.ledger-cell .value.ok {{ color: {COLOR_LEDGER_GREEN}; }}
.ledger-cell .label {{
    font-size: 0.78rem;
    color: {COLOR_INK_SOFT};
    margin-top: 4px;
}}

/* ---- Status pill (sidebar) -------------------------------------------- */
.status-pill {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    font-size: 0.88rem;
}}
.status-dot {{
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}}
.status-dot.ok {{ background: {COLOR_LEDGER_GREEN}; }}
.status-dot.warn {{ background: {COLOR_BRASS}; }}
.status-dot.error {{ background: {COLOR_CLAY}; }}

.config-line {{
    font-family: {FONT_MONO};
    font-size: 0.78rem;
    color: {COLOR_INK_SOFT};
    padding: 2px 0;
    word-break: break-word;
}}
.config-line b {{ color: {COLOR_INK}; font-weight: 500; }}

/* ---- Dossier panels (hierarchy view) ----------------------------------- */
.dossier-section {{
    font-family: {FONT_SERIF};
    font-size: 1.15rem;
    font-weight: 600;
    color: {COLOR_INK};
    margin: 22px 0 8px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid {COLOR_RULE};
}}
.dossier-subsection {{
    font-size: 0.82rem;
    text-transform: none;
    color: {COLOR_INK_SOFT};
    margin: 14px 0 6px 2px;
    font-weight: 500;
}}
.dossier-card {{
    border-left: 3px solid {COLOR_BRASS};
    background: {COLOR_PAPER_RAISED};
    border-top: 1px solid {COLOR_RULE};
    border-right: 1px solid {COLOR_RULE};
    border-bottom: 1px solid {COLOR_RULE};
    padding: 12px 16px;
    margin-bottom: 10px;
}}
.dossier-card.flagged {{ border-left-color: {COLOR_CLAY}; }}
.dossier-card .req-id {{
    font-family: {FONT_MONO};
    font-size: 0.76rem;
    color: {COLOR_BRASS};
    background: {COLOR_BRASS_SOFT};
    padding: 1px 6px;
    display: inline-block;
    margin-bottom: 6px;
}}
.dossier-card.flagged .req-id {{
    color: {COLOR_CLAY};
    background: {COLOR_CLAY_SOFT};
}}
.dossier-card .req-text {{
    font-size: 0.95rem;
    color: {COLOR_INK};
    line-height: 1.45;
}}
.dossier-card .req-meta {{
    font-family: {FONT_MONO};
    font-size: 0.74rem;
    color: {COLOR_INK_SOFT};
    margin-top: 8px;
}}
.dossier-card .req-flag {{
    font-size: 0.76rem;
    color: {COLOR_CLAY};
    margin-top: 6px;
}}

/* ---- Streamlit chrome, restyled --------------------------------------- */
[data-testid="stSidebar"] {{
    background: {COLOR_PAPER_RAISED};
    border-right: 1px solid {COLOR_RULE};
}}
[data-testid="stSidebar"] h3 {{
    font-family: {FONT_SANS};
    font-size: 0.82rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: {COLOR_INK_SOFT};
}}

.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    border-bottom: 1px solid {COLOR_RULE};
}}
.stTabs [data-baseweb="tab"] {{
    font-family: {FONT_SANS};
    font-weight: 500;
    color: {COLOR_INK_SOFT};
}}
.stTabs [aria-selected="true"] {{
    color: {COLOR_INK} !important;
    border-bottom-color: {COLOR_BRASS} !important;
}}

button[kind="primary"], .stButton > button[kind="primary"] {{
    background-color: {COLOR_BRASS} !important;
    border-color: {COLOR_BRASS} !important;
    color: {COLOR_PAPER} !important;
    border-radius: 2px !important;
    font-weight: 500;
}}
button[kind="primary"]:hover {{
    background-color: {COLOR_INK} !important;
    border-color: {COLOR_INK} !important;
}}

[data-testid="stFileUploaderDropzone"] {{
    background: {COLOR_PAPER_RAISED};
    border: 1px dashed {COLOR_RULE} !important;
    border-radius: 2px;
}}

[data-testid="stExpander"] {{
    border: 1px solid {COLOR_RULE} !important;
    border-radius: 2px !important;
    background: {COLOR_PAPER_RAISED};
}}

div[data-testid="stStatusWidget"] {{
    border: 1px solid {COLOR_RULE} !important;
    border-radius: 2px !important;
    font-family: {FONT_MONO};
    font-size: 0.85rem;
}}

[data-testid="stDataFrame"], [data-testid="stDataEditor"] {{
    border: 1px solid {COLOR_RULE} !important;
}}
</style>
"""


# ---------------------------------------------------------------------------
# Reusable HTML fragments
# ---------------------------------------------------------------------------
_MARK_SVG = """
<svg width="34" height="34" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M7 2H21L27 8V32H7V2Z" stroke="#16233B" stroke-width="1.6" fill="#FAF7F1"/>
  <path d="M21 2V8H27" stroke="#16233B" stroke-width="1.6" fill="none"/>
  <line x1="11" y1="15" x2="23" y2="15" stroke="#16233B" stroke-width="1.3"/>
  <line x1="11" y1="19.5" x2="23" y2="19.5" stroke="#16233B" stroke-width="1.3"/>
  <line x1="11" y1="24" x2="18" y2="24" stroke="#9C6B2E" stroke-width="1.8"/>
</svg>
""".strip()


def render_letterhead(title: str, tagline: str) -> None:
    """A document-style header: mark, title, one-line tagline."""
    st.markdown(
        f"""
        <div class="dossier-letterhead">
            <div class="mark">{_MARK_SVG}</div>
            <div class="titles">
                <h1>{title}</h1>
                <p>{tagline}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ledger_strip(stats: List[Dict[str, Any]]) -> None:
    """
    A single horizontal strip of figures divided by hairlines, in place of a
    row of identical rounded metric cards.

    Each item: {"value": "41", "label": "Requirements", "tone": "flag"|"ok"|None}
    """
    cells = []
    for item in stats:
        tone_class = f" {item['tone']}" if item.get("tone") else ""
        cells.append(
            f'<div class="ledger-cell">'
            f'<div class="value{tone_class}">{item["value"]}</div>'
            f'<div class="label">{item["label"]}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="ledger-strip">{"".join(cells)}</div>', unsafe_allow_html=True)


def render_status_pill(state: str, text: str) -> None:
    """state is 'ok', 'warn' or 'error' - a small dot instead of a full-width alert box."""
    st.markdown(
        f'<div class="status-pill"><span class="status-dot {state}"></span>{text}</div>',
        unsafe_allow_html=True,
    )


def render_config_line(label: str, value: str) -> None:
    st.markdown(f'<div class="config-line"><b>{label}</b> &nbsp; {value}</div>', unsafe_allow_html=True)


def render_dossier_card(record: Dict[str, Any], format_pages_fn) -> None:
    """One requirement, styled as a filed record rather than a markdown bullet."""
    flagged = bool(record.get("review_required"))
    css_class = "dossier-card flagged" if flagged else "dossier-card"

    flag_html = ""
    if flagged:
        reasons = "; ".join(record.get("review_reasons") or []) or "Flagged for review."
        flag_html = f'<div class="req-flag">Review required. {reasons}</div>'

    st.markdown(
        f"""
        <div class="{css_class}">
            <span class="req-id">{record.get('requirement_id', '')}</span>
            <div class="req-text">{record.get('requirement', '')}</div>
            <div class="req-meta">Source page {format_pages_fn(record.get('source_pages'))}
                &nbsp; &nbsp; Confidence: {record.get('confidence', '')}</div>
            {flag_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
