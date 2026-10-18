import io
from dataclasses import dataclass

from pypdf import PdfReader

MIN_CHARS_PER_PAGE = 100


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class Extraction:
    pages: list[PageText]
    total_chars: int
    needs_ocr: bool


def extract_pages(content: bytes) -> Extraction:
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").replace("\x00", "").strip()
        pages.append(PageText(page_number=number, text=text))

    total_chars = sum(len(page.text) for page in pages)
    needs_ocr = not pages or total_chars / len(pages) < MIN_CHARS_PER_PAGE
    return Extraction(pages=pages, total_chars=total_chars, needs_ocr=needs_ocr)
