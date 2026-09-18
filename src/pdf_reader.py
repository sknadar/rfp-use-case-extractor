"""
pdf_reader.py
=============

Single responsibility: turn an uploaded PDF into page-level text.

The most important rule in this file is: **never lose the page number.**
Every requirement we extract later must be traceable back to a page, so the
page number travels with the text from the very first step.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List, Sequence

from pypdf import PdfReader
from pypdf.errors import PdfReadError as PyPdfReadError

from src.logging_config import get_logger

logger = get_logger(__name__)

PDF_MAGIC = b"%PDF-"


# ---------------------------------------------------------------------------
# Errors. Each one carries a message that is safe to show to a normal user.
# ---------------------------------------------------------------------------
class PdfValidationError(Exception):
    """Base class for every problem with the uploaded file."""


class EmptyFileError(PdfValidationError):
    pass


class NotAPdfError(PdfValidationError):
    pass


class CorruptPdfError(PdfValidationError):
    pass


class EncryptedPdfError(PdfValidationError):
    pass


class NoTextFoundError(PdfValidationError):
    """The PDF opened fine but contains no machine-readable text (likely scanned)."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class PdfPage:
    """The text of exactly one PDF page."""

    page_number: int   # 1-based, the number a human sees in a PDF viewer
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass
class PdfDocument:
    """The whole document, still split page by page."""

    file_name: str
    pages: List[PdfPage] = field(default_factory=list)
    empty_page_numbers: List[int] = field(default_factory=list)
    likely_scanned: bool = False

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def total_chars(self) -> int:
        return sum(page.char_count for page in self.pages)

    def page_numbers(self) -> List[int]:
        return [page.page_number for page in self.pages]


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------
def validate_pdf_bytes(data: bytes, file_name: str, max_mb: int = 50) -> None:
    """
    Cheap checks before we even try to parse the file.

    Doing this first means an obviously wrong file fails fast with a clear
    message instead of producing a confusing library traceback.
    """
    if data is None or len(data) == 0:
        raise EmptyFileError("The uploaded file is empty (0 bytes).")

    if not file_name.lower().endswith(".pdf"):
        raise NotAPdfError("Only .pdf files are supported.")

    if not data.startswith(PDF_MAGIC):
        raise NotAPdfError(
            "This file does not look like a real PDF. "
            "It may have been renamed from another format."
        )

    size_mb = len(data) / (1024 * 1024)
    if size_mb > max_mb:
        raise PdfValidationError(
            f"The file is {size_mb:.1f} MB, which is larger than the "
            f"{max_mb} MB limit for this application."
        )


def _clean_page_text(text: str) -> str:
    """Tidy up extracted text without changing any words."""
    if not text:
        return ""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    # Collapse runs of blank lines into a single blank line.
    cleaned: List[str] = []
    blank_run = 0
    for line in lines:
        if line.strip() == "":
            blank_run += 1
            if blank_run > 1:
                continue
        else:
            blank_run = 0
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def read_pdf(
    data: bytes,
    file_name: str,
    max_mb: int = 50,
    min_chars_per_page: int = 25,
) -> PdfDocument:
    """
    Read a PDF from raw bytes and return one `PdfPage` per physical page.

    Raises a `PdfValidationError` subclass for every foreseeable problem so the
    UI can show one friendly sentence instead of a stack trace.
    """
    validate_pdf_bytes(data, file_name, max_mb=max_mb)

    try:
        reader = PdfReader(io.BytesIO(data))
    except PyPdfReadError as exc:
        raise CorruptPdfError(
            "The PDF could not be opened. It may be damaged or incomplete."
        ) from exc
    except Exception as exc:  # any other parsing failure
        raise CorruptPdfError("The PDF could not be opened.") from exc

    if getattr(reader, "is_encrypted", False):
        # Many PDFs are encrypted with an empty owner password; try that first.
        try:
            if reader.decrypt("") == 0:
                raise EncryptedPdfError(
                    "This PDF is password protected. Please upload an unlocked copy."
                )
        except EncryptedPdfError:
            raise
        except Exception as exc:
            raise EncryptedPdfError(
                "This PDF is password protected. Please upload an unlocked copy."
            ) from exc

    if len(reader.pages) == 0:
        raise EmptyFileError("The PDF contains no pages.")

    document = PdfDocument(file_name=file_name)

    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            # One unreadable page must not kill the whole run.
            logger.warning("Could not extract text from page %s: %s", index, exc)
            text = ""

        text = _clean_page_text(text)
        document.pages.append(PdfPage(page_number=index, text=text))
        if len(text) < min_chars_per_page:
            document.empty_page_numbers.append(index)

    logger.info(
        "PDF pages extracted | pages=%s | characters=%s | empty_pages=%s",
        document.page_count,
        document.total_chars,
        len(document.empty_page_numbers),
    )

    if document.total_chars == 0:
        raise NoTextFoundError(
            "No readable text was found in this PDF. It is probably a scanned "
            "document (images of text). OCR support is not part of this version."
        )

    # More than 70% of pages effectively blank -> warn, but keep going.
    if len(document.empty_page_numbers) > 0.7 * document.page_count:
        document.likely_scanned = True
        logger.warning("Document looks partially scanned: %s", document.file_name)

    return document


# ---------------------------------------------------------------------------
# Batching: prepare content for the model without losing page markers
# ---------------------------------------------------------------------------
PAGE_MARKER = "=== PAGE {page} ==="


def format_pages_for_prompt(pages: Sequence[PdfPage]) -> str:
    """
    Join pages into one string, each preceded by an explicit page marker.

    Gemini can only give us correct page numbers if it can *see* them, so the
    marker format here must match the format described in the prompt.
    """
    blocks = []
    for page in pages:
        body = page.text if page.text.strip() else "[no readable text on this page]"
        blocks.append(f"{PAGE_MARKER.format(page=page.page_number)}\n{body}")
    return "\n\n".join(blocks)


def build_batches(
    pages: Sequence[PdfPage], char_budget: int = 45_000
) -> List[List[PdfPage]]:
    """
    Split the document into groups of whole pages that fit a character budget.

    Why batch at all? A 300-page RFP is both expensive and hard for any model to
    handle accurately in one shot. Batching keeps each request focused, which
    improves extraction quality and page attribution.

    A page is never split in half — page boundaries stay intact, and no content
    is ever dropped (nothing is silently truncated).
    """
    if char_budget <= 0:
        raise ValueError("char_budget must be positive")

    batches: List[List[PdfPage]] = []
    current: List[PdfPage] = []
    current_chars = 0

    for page in pages:
        # +40 roughly accounts for the page marker line.
        page_cost = page.char_count + 40
        if current and current_chars + page_cost > char_budget:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(page)
        current_chars += page_cost

    if current:
        batches.append(current)

    return batches
