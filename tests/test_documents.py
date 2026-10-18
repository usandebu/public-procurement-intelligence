import io

import pytest
from pypdf import PdfWriter

from procurement.documents import doc_id, extract_pages, is_pdf


def build_pdf(pages: list[str]) -> bytes:
    font_id = 3 + 2 * len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>",
    ]
    for i, text in enumerate(pages):
        page_id = 3 + 2 * i
        stream = f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET"
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 200] "
            f"/Contents {page_id + 1} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    body = "%PDF-1.4\n"
    offsets = []
    for number, content in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n{content}\nendobj\n"
    xref_at = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        body += f"{offset:010d} 00000 n \n"
    body += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    return body.encode("latin-1")


def blank_pdf(pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


LONG_TEXT = (
    "Pliego de clausulas administrativas particulares del contrato de servicios " * 3
)


def test_extract_pages_returns_text_with_page_numbers():
    extraction = extract_pages(build_pdf([LONG_TEXT, LONG_TEXT.upper()]))

    assert [p.page_number for p in extraction.pages] == [1, 2]
    assert "Pliego de clausulas" in extraction.pages[0].text
    assert "PLIEGO DE CLAUSULAS" in extraction.pages[1].text
    assert extraction.total_chars == sum(len(p.text) for p in extraction.pages)
    assert extraction.needs_ocr is False


def test_extract_pages_flags_documents_without_text_layer():
    extraction = extract_pages(blank_pdf(3))

    assert len(extraction.pages) == 3
    assert extraction.total_chars == 0
    assert extraction.needs_ocr is True


def test_extract_pages_rejects_content_that_is_not_a_pdf():
    with pytest.raises(Exception):  # noqa: B017
        extract_pages(b"this is not a pdf")


def test_is_pdf_checks_the_header():
    assert is_pdf(b"%PDF-1.7 rest")
    assert not is_pdf(b"<html>error page</html>")


def test_doc_id_is_deterministic_and_depends_on_uri_and_hash():
    assert doc_id("u", "h") == doc_id("u", "h")
    assert doc_id("u", "h") != doc_id("u", "other")
    assert doc_id("u", None) == doc_id("u", "")
