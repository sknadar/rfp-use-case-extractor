"""Tests for pdf_reader.py: validation, page preservation and batching."""

from __future__ import annotations

import pytest

from src.pdf_reader import (
    EmptyFileError,
    NoTextFoundError,
    NotAPdfError,
    PdfPage,
    build_batches,
    format_pages_for_prompt,
    read_pdf,
)


def test_reads_every_page_and_keeps_numbers(pdf_bytes):
    document = read_pdf(pdf_bytes, "sample.pdf")

    assert document.page_count == 2
    assert document.page_numbers() == [1, 2]
    assert "account balance" in document.pages[0].text
    assert "monthly transaction reports" in document.pages[1].text


def test_empty_file_is_rejected():
    with pytest.raises(EmptyFileError):
        read_pdf(b"", "empty.pdf")


def test_non_pdf_extension_is_rejected():
    with pytest.raises(NotAPdfError):
        read_pdf(b"%PDF-1.4 something", "notes.txt")


def test_file_that_is_not_really_a_pdf_is_rejected():
    with pytest.raises(NotAPdfError):
        read_pdf(b"this is plain text", "fake.pdf")


def test_oversized_file_is_rejected(pdf_bytes):
    with pytest.raises(Exception):
        read_pdf(pdf_bytes, "sample.pdf", max_mb=0)


def test_pdf_without_text_is_reported(blank_pdf_bytes):
    with pytest.raises(NoTextFoundError):
        read_pdf(blank_pdf_bytes, "scan.pdf")


def test_page_markers_are_included_in_the_prompt():
    pages = [PdfPage(page_number=7, text="Requirement A"), PdfPage(page_number=8, text="Requirement B")]
    rendered = format_pages_for_prompt(pages)

    assert "=== PAGE 7 ===" in rendered
    assert "=== PAGE 8 ===" in rendered
    assert rendered.index("=== PAGE 7 ===") < rendered.index("=== PAGE 8 ===")


def test_batching_never_splits_a_page_and_never_drops_content():
    pages = [PdfPage(page_number=i, text="x" * 400) for i in range(1, 11)]
    batches = build_batches(pages, char_budget=1000)

    assert len(batches) > 1
    flattened = [page.page_number for batch in batches for page in batch]
    assert flattened == list(range(1, 11))       # nothing lost, order preserved


def test_single_batch_when_document_is_small():
    pages = [PdfPage(page_number=1, text="short"), PdfPage(page_number=2, text="short")]
    assert len(build_batches(pages, char_budget=45_000)) == 1
