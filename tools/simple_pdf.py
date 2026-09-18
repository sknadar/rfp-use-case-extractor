"""
simple_pdf.py
=============

A tiny, dependency-free PDF writer.

It exists for two reasons only:
* the unit tests need real PDF bytes without installing a PDF-authoring library;
* `tools/make_sample_pdf.py` uses it to produce a demo RFP you can upload.

It is NOT part of the application pipeline. Do not use it for production PDFs.
"""

from __future__ import annotations

from typing import List, Sequence

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT_MARGIN = 56
TOP_START = 736
LINE_HEIGHT = 16
FONT_SIZE = 11
MAX_CHARS_PER_LINE = 88


def _escape(text: str) -> str:
    """Escape the three characters that are special inside a PDF string."""
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _wrap(text: str, width: int = MAX_CHARS_PER_LINE) -> List[str]:
    """Very simple word wrap so long sentences stay on the page."""
    lines: List[str] = []
    for raw_line in text.split("\n"):
        words = raw_line.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            if len(current) + 1 + len(word) <= width:
                current = f"{current} {word}"
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _content_stream(text: str) -> bytes:
    """Build the drawing instructions for one page."""
    parts = ["BT", f"/F1 {FONT_SIZE} Tf", f"{LINE_HEIGHT} TL", f"1 0 0 1 {LEFT_MARGIN} {TOP_START} Tm"]
    for line in _wrap(text):
        parts.append(f"({_escape(line)}) Tj")
        parts.append("T*")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", errors="replace")


def make_pdf(pages: Sequence[str]) -> bytes:
    """Return the bytes of a valid, uncompressed, text-based PDF."""
    if not pages:
        raise ValueError("A PDF needs at least one page.")

    objects: List[bytes] = []          # objects[i] is object number i+1
    page_count = len(pages)

    # Object numbering: 1 = catalog, 2 = pages tree, 3 = font,
    # then for each page: a page object and a content object.
    font_obj_num = 3
    first_page_obj = 4
    page_obj_numbers = [first_page_obj + 2 * i for i in range(page_count)]
    content_obj_numbers = [num + 1 for num in page_obj_numbers]

    kids = " ".join(f"{num} 0 R" for num in page_obj_numbers)

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for index, text in enumerate(pages):
        stream = _content_stream(text)
        page_dict = (
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font_obj_num} 0 R >> >> "
            f"/Contents {content_obj_numbers[index]} 0 R >>"
        ).encode()
        objects.append(page_dict)
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )

    # Assemble the file, recording the byte offset of every object for the xref.
    out = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()

    return bytes(out)
